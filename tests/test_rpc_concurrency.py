"""Real sandbox concurrency and bounded generic scheduling instrumentation."""

import os
import sqlite3
import threading
import time

import pytest

from benchmark.templates import create_template
from evaluator.rpc import BusinessRPC, RemoteBusinessError
from evaluator.worker import execute_batch


def purchase_operations(count, *, quantity=1, prefix="purchase"):
    return [{"method": "create_order", "params": {
        "order_id": f"{prefix}-{index}", "sku": "widget", "quantity": quantity,
    }} for index in range(count)]


def assert_real_concurrent_execution(batch, count):
    execution = batch["execution"]
    assert execution["operations"] == count
    assert execution["max_active"] > 1
    assert len(execution["thread_ids"]) > 1
    assert len(batch["results"]) == count
    assert [result["index"] for result in batch["results"]] == list(range(count))
    assert {result["pid"] for result in batch["results"]} == {execution["pid"]}
    assert {result["thread_id"] for result in batch["results"]} == set(execution["thread_ids"])
    assert all(result["end_ns"] >= result["start_ns"] > 0 for result in batch["results"])


def database_totals(data_dir):
    # Developer checks read actual storage instead of relying on candidate audit().
    with sqlite3.connect(data_dir / "business.sqlite") as connection:
        inventory = connection.execute(
            "SELECT available, reserved FROM inventory WHERE sku = 'widget'"
        ).fetchone()
        orders = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM orders "
            "WHERE reservation_state = 'active'"
        ).fetchone()
        ledger = connection.execute(
            "SELECT COALESCE(SUM(reserved_delta), 0) FROM inventory_ledger"
        ).fetchone()[0]
    return inventory, orders, ledger


def test_reference_rpc_batch_has_real_threads_and_independent_business_results(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    data_dir = tmp_path / "data"
    rpc = BusinessRPC(workspace, data_dir, tmp_path / "worker.log").start()
    try:
        rpc.call("initialize", stock={"widget": 50}, reset=True)
        batch = rpc.batch(purchase_operations(200), max_workers=32)
        assert_real_concurrent_execution(batch, 200)
        successful = [result for result in batch["results"] if result["ok"]]
        unsuccessful = [result for result in batch["results"] if not result["ok"]]
        assert len(successful) == 50
        assert len(unsuccessful) == 150
        assert all(result["error"]["type"] == "InsufficientInventory" for result in unsuccessful)
        assert batch["execution"]["checkpoint"] is None
        assert database_totals(data_dir) == ((0, 50), (50, 50), 50)
        # The version-1 sequential endpoint and same flow remain usable afterward.
        assert rpc.call("get_inventory", sku="widget")["available"] == 0
    finally:
        rpc.close()


def test_checkpoint_is_optional_for_correct_candidate(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    rpc = BusinessRPC(workspace, tmp_path / "data", tmp_path / "worker.log").start()
    try:
        rpc.call("initialize", stock={"widget": 7}, reset=True)
        batch = rpc.batch(purchase_operations(20), max_workers=8,
                          checkpoint={"label": "inventory_read", "timeout_seconds": 0.2})
        assert_real_concurrent_execution(batch, 20)
        assert sum(result["ok"] for result in batch["results"]) == 7
        assert batch["execution"]["checkpoint"]["arrivals"] == 0
        assert batch["execution"]["checkpoint"]["released_by"] == "unused"
    finally:
        rpc.close()


def test_batch_does_not_turn_one_business_error_into_whole_batch_error(tmp_path):
    workspace = create_template(tmp_path / "candidate", buggy=False)
    rpc = BusinessRPC(workspace, tmp_path / "data", tmp_path / "worker.log").start()
    try:
        rpc.call("initialize", stock={"widget": 2}, reset=True)
        operations = purchase_operations(3)
        operations[1]["params"]["quantity"] = 0
        operations[2]["params"]["quantity"] = 3
        batch = rpc.batch(operations, max_workers=3)
        assert [result["ok"] for result in batch["results"]] == [True, False, False]
        assert batch["results"][1]["error"]["type"] == "InvalidInput"
        assert batch["results"][2]["error"]["type"] == "InsufficientInventory"
        assert rpc.call("get_inventory", sku="widget")["available"] == 1
        with pytest.raises(RemoteBusinessError) as error:
            rpc.call("get_order", order_id="missing")
        assert error.value.kind == "OrderNotFound"
    finally:
        rpc.close()


def test_episode_a_snapshot_gate_exposes_real_lost_updates(tmp_path):
    from benchmark.episodes.episode_a import create_episode_a

    workspace = create_episode_a(tmp_path / "candidate", buggy=True)
    data_dir = tmp_path / "data"
    rpc = BusinessRPC(workspace, data_dir, tmp_path / "worker.log").start()
    try:
        rpc.call("initialize", stock={"widget": 8}, reset=True)
        batch = rpc.batch(purchase_operations(8), max_workers=8,
                          checkpoint={"label": "inventory_read", "timeout_seconds": 2.0})
        assert_real_concurrent_execution(batch, 8)
        gate = batch["execution"]["checkpoint"]
        assert gate["arrivals"] == gate["parties"] == 8
        assert gate["released_by"] == "all_arrived"
        assert gate["waiters_peak"] >= 2
        assert all(result["ok"] for result in batch["results"])
        inventory, orders, ledger = database_totals(data_dir)
        assert orders == (8, 8)
        assert ledger == 8
        assert inventory[1] != orders[1]
    finally:
        rpc.close()


def test_episode_a_serialized_repair_is_not_forced_to_deadlock(tmp_path):
    from benchmark.episodes.episode_a import create_episode_a

    workspace = create_episode_a(tmp_path / "candidate", buggy=True)
    service = workspace / "app" / "service.py"
    service.write_text(service.read_text() + """

# A developer-only alternate strategy proves the scheduling gate is permissive.
import threading
_create_lock = threading.RLock()
_unlocked_create = OrderFlow.create_order
def _serialized_create(self, *args, **kwargs):
    with _create_lock:
        return _unlocked_create(self, *args, **kwargs)
OrderFlow.create_order = _serialized_create
""", encoding="utf-8")
    data_dir = tmp_path / "data"
    rpc = BusinessRPC(workspace, data_dir, tmp_path / "worker.log").start()
    try:
        rpc.call("initialize", stock={"widget": 12}, reset=True)
        batch = rpc.batch(purchase_operations(30), max_workers=8,
                          checkpoint={"label": "inventory_read", "timeout_seconds": 0.3})
        assert_real_concurrent_execution(batch, 30)
        assert batch["execution"]["checkpoint"]["released_by"] == "timeout"
        assert sum(result["ok"] for result in batch["results"]) == 12
        assert all(result["error"]["type"] == "InsufficientInventory"
                   for result in batch["results"] if not result["ok"])
        assert database_totals(data_dir) == ((0, 12), (12, 12), 12)
    finally:
        rpc.close()


def test_generic_gate_only_synchronizes_first_wave_and_uses_observed_ids():
    class Candidate:
        def operation(self, value):
            self._schedule_checkpoint("read")
            return value

    candidate = Candidate()
    operations = [{"method": "operation", "params": {"value": index}} for index in range(40)]
    batch = execute_batch(candidate, {"operation": candidate.operation}, operations,
                          max_workers=4, checkpoint={"label": "read", "timeout_seconds": 1.0})
    assert_real_concurrent_execution(batch, 40)
    assert batch["execution"]["pid"] == os.getpid()
    assert batch["execution"]["checkpoint"]["arrivals"] == 4
    assert batch["execution"]["checkpoint"]["released_by"] == "all_arrived"
    assert [result["result"] for result in batch["results"]] == list(range(40))
    assert not hasattr(candidate, "_schedule_checkpoint")


def test_generic_gate_restores_existing_hook_and_reports_real_exception():
    class Candidate:
        _schedule_checkpoint = lambda self, label: None

        def operation(self, value):
            self._schedule_checkpoint("read")
            if value == 2:
                raise LookupError("demonstration business rejection")
            return value

    candidate = Candidate()
    previous = candidate._schedule_checkpoint
    batch = execute_batch(candidate, {"operation": candidate.operation},
                          [{"method": "operation", "params": {"value": index}} for index in range(4)],
                          max_workers=4, checkpoint={"label": "read"})
    assert candidate._schedule_checkpoint == previous
    assert batch["results"][2]["ok"] is False
    assert batch["results"][2]["error"]["type"] == "LookupError"
    assert sum(result["ok"] for result in batch["results"]) == 3


def test_checkpoint_timeout_is_bounded_for_serialized_calls():
    class Candidate:
        def __init__(self):
            self.lock = threading.Lock()

        def operation(self):
            with self.lock:
                self._schedule_checkpoint("read")
                return "done"

    candidate = Candidate()
    started = time.monotonic()
    batch = execute_batch(candidate, {"operation": candidate.operation},
                          [{"method": "operation"} for _ in range(12)], max_workers=4,
                          checkpoint={"label": "read", "timeout_seconds": 0.1})
    assert time.monotonic() - started < 3.0
    assert all(result["ok"] for result in batch["results"])
    assert batch["execution"]["checkpoint"]["released_by"] == "timeout"
    assert batch["execution"]["checkpoint"]["waiters_peak"] == 1


@pytest.mark.parametrize("parameters", [
    {"operations": []},
    {"operations": [{"method": "operation"}] * 1001},
    {"max_workers": 0},
    {"max_workers": 257},
    {"max_workers": True},
    {"synchronize_start": 1},
    {"operations": [{"method": "unknown"}]},
    {"operations": [{"method": "operation", "params": []}]},
    {"checkpoint": {"label": ""}},
    {"checkpoint": {"label": "read", "timeout_seconds": -1}},
    {"checkpoint": {"label": "read", "timeout_seconds": float("nan")}},
])
def test_batch_validates_resource_limits_and_generic_request_shape(parameters):
    class Candidate:
        def operation(self):
            return None

    candidate = Candidate()
    arguments = {"operations": [{"method": "operation"}], "max_workers": 1}
    arguments.update(parameters)
    with pytest.raises(ValueError):
        execute_batch(candidate, {"operation": candidate.operation}, **arguments)
