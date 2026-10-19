"""Independent D checks read real trusted fixture DBs, never candidate code."""

import hashlib
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys

import pytest

from app.service import OrderFlow
from evaluator.episode_d_oracle import (
    inspect_episode_d_database, recover_episode_d_database,
)


@pytest.fixture
def stored(tmp_path):
    path = tmp_path / "business.sqlite"
    flow = OrderFlow(path)
    flow.initialize({"alpha": 10, "beta": 7})
    return path, flow


def inspect(path, **kwargs):
    return inspect_episode_d_database(path, expected_stock={"alpha": 10, "beta": 7},
                                      data_dir=path.parent, **kwargs)


def request(order_id="first", *, sku="alpha", quantity=2):
    return {"method": "create_order", "params": {
        "order_id": order_id, "sku": sku, "quantity": quantity,
    }}


def response(index, row, worker=0):
    return {"index": index, "worker_index": worker, "host_pid": 100 + worker,
            "start_ns": 1, "end_ns": 2, "ok": True, "result": row}


def test_d_row_oracle_reuses_all_independent_constraints(stored):
    path, _ = stored
    before = path.read_bytes()
    oracle = inspect(path)
    assert oracle["consistent"] is True
    assert oracle["episode_d_oracle_version"] == "1.0.0"
    assert all(probe["rejected"] for probe in oracle["constraint_probes"])
    assert oracle["response_checks"]["available"] is False
    assert path.read_bytes() == before


def test_d_response_and_written_witness_match_actual_orders(stored):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    second = flow.create_order("second", "beta", 1)
    result = inspect(path, requests=[request(), request("second", sku="beta", quantity=1)],
                     results=[response(0, first, 0), response(1, second, 1)],
                     required_worker_ids=[0, 1], expected_order_ids={"first", "second"})
    assert result["consistent"] is True, result["violations"]
    assert result["write_witness"]["verified"] is True
    assert result["write_witness"]["per_worker_order_ids"] == {"0": ["first"], "1": ["second"]}


def test_duplicate_retry_does_not_claim_multiple_worker_writes(stored):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    result = inspect(path, requests=[request(), request()],
                     results=[response(0, first, 0), response(1, first, 1)],
                     required_worker_ids=[0, 1])
    assert result["consistent"] is False
    assert result["response_checks"]["all_match"] is True
    assert result["response_checks"]["successful"] == 2
    assert result["response_checks"]["unique_successful_order_ids"] == ["first"]
    assert len(result["orders"]) == len(result["ledger"]) == 1
    assert result["write_witness"]["missing_worker_ids"] == [0, 1]


def test_idempotent_retries_are_valid_when_not_used_as_new_write_witness(stored):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    result = inspect(path, requests=[request(), request()],
                     results=[response(0, first), response(1, first, 1)],
                     expected_orders={"first": {"sku": "alpha", "quantity": 2,
                                                "status": "reserved"}})
    assert result["consistent"] is True
    assert len(result["orders"]) == len(result["ledger"]) == 1
    assert result["inventory"][0]["reserved"] == 2


@pytest.mark.parametrize("row", [None, {}, {"order_id": "first", "sku": "alpha", "quantity": 2}])
def test_successful_response_without_actual_commit_is_rejected(stored, row):
    path, _ = stored
    result = inspect(path, requests=[request()], results=[response(0, row)])
    assert result["consistent"] is False
    assert any("no matching durable order" in violation for violation in result["violations"])


def test_candidate_returned_content_cannot_override_database(stored):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    false = dict(first, quantity=3)
    result = inspect(path, requests=[request()], results=[response(0, false)])
    assert result["consistent"] is False
    assert any("contents differ from storage" in violation for violation in result["violations"])


@pytest.mark.parametrize("method,params", [
    ("create_order", {"order_id": "first", "sku": "alpha", "quantity": 2}),
    ("reserve_inventory", {"order_id": "first"}),
    ("cancel_order", {"order_id": "first"}),
    ("release_inventory", {"order_id": "first"}),
])
@pytest.mark.parametrize("state", [("invented", "active"), ("reserved", "none"),
                                   (None, "active"), (["reserved"], "active")])
def test_invalid_successful_api_states_are_rejected(stored, method, params, state):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    false = dict(first, status=state[0], reservation_state=state[1])
    result = inspect(path, requests=[{"method": method, "params": params}],
                     results=[response(0, false)])
    assert result["consistent"] is False
    assert any("invalid state for its API operation" in violation for violation in result["violations"])


@pytest.mark.parametrize("method,state", [
    ("create_order", ("created", "none")),
    ("reserve_inventory", ("created", "none")),
    ("reserve_inventory", ("cancelled", "released")),
    ("cancel_order", ("reserved", "active")),
    ("release_inventory", ("reserved", "active")),
])
def test_legal_state_of_wrong_operation_cannot_be_success(stored, method, state):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    false = dict(first, status=state[0], reservation_state=state[1])
    params = request()["params"] if method == "create_order" else {"order_id": "first"}
    result = inspect(path, requests=[{"method": method, "params": params}],
                     results=[response(0, false)])
    assert result["consistent"] is False
    assert any("invalid state for its API operation" in violation for violation in result["violations"])


def test_reserved_create_response_remains_valid_after_later_cancel(stored):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    flow.cancel_order("first")
    result = inspect(path, requests=[request()], results=[response(0, first)])
    assert result["consistent"] is True, result["violations"]
    assert result["orders"][0]["status"] == "cancelled"
    assert result["response_checks"]["all_match"] is True


@pytest.mark.parametrize("initially_reserved", [False, True])
@pytest.mark.parametrize("reserve_retry", [False, True])
def test_create_retry_can_return_cancelled_order_without_faking_new_write(
        stored, initially_reserved, reserve_retry):
    path, flow = stored
    flow.create_order("first", "alpha", 2, reserve=initially_reserved)
    cancelled = flow.cancel_order("first")
    traffic = request()
    traffic["params"]["reserve"] = reserve_retry
    result = inspect(path, requests=[traffic], results=[response(0, cancelled)])
    assert result["consistent"] is True, result["violations"]
    assert result["write_witness"]["per_worker_order_ids"] == {}


def test_create_without_reserve_can_return_created_or_existing_reserved(stored):
    path, flow = stored
    created = flow.create_order("first", "alpha", 2, reserve=False)
    flow.reserve_inventory("first")
    reserved = flow.get_order("first")
    traffic = request()
    traffic["params"]["reserve"] = False
    result = inspect(path, requests=[traffic, traffic],
                     results=[response(0, created), response(1, reserved)])
    assert result["consistent"] is True, result["violations"]


@pytest.mark.parametrize("method", ["cancel_order", "release_inventory"])
@pytest.mark.parametrize("initially_reserved", [False, True])
def test_cancel_and_release_valid_api_states(stored, method, initially_reserved):
    path, flow = stored
    flow.create_order("first", "alpha", 2, reserve=initially_reserved)
    flow.cancel_order("first")
    row = getattr(flow, method)("first")
    result = inspect(path, requests=[{"method": method, "params": {"order_id": "first"}}],
                     results=[response(0, row)])
    assert result["consistent"] is True, result["violations"]


def test_reserve_response_is_valid_even_if_subsequently_cancelled(stored):
    path, flow = stored
    flow.create_order("first", "alpha", 2, reserve=False)
    reserved = flow.reserve_inventory("first")
    flow.cancel_order("first")
    result = inspect(path, requests=[{"method": "reserve_inventory", "params": {"order_id": "first"}}],
                     results=[response(0, reserved)])
    assert result["consistent"] is True, result["violations"]


def test_split_ledger_persistent_state_is_rejected(stored):
    path, flow = stored
    first = flow.create_order("first", "alpha", 2)
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM inventory_ledger WHERE order_id = 'first'")
    result = inspect(path, requests=[request()], results=[response(0, first)])
    assert result["consistent"] is False
    assert "Order reservation differs from ledger: first" in result["violations"]
    assert any("no durable reserve ledger" in violation for violation in result["violations"])


def test_lost_update_rows_are_rejected_even_with_conserving_inventory(stored):
    path, flow = stored
    flow.create_order("first", "alpha", 2)
    flow.create_order("second", "alpha", 3)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE inventory SET available = 7, reserved = 3 WHERE sku = 'alpha'")
    result = inspect(path)
    assert result["consistent"] is False
    assert "alpha: ledger_matches failed" in result["violations"]
    assert "alpha: order_reservations_match failed" in result["violations"]


@pytest.mark.parametrize("kind", ["OperationalError", "ProcessExited", "InventedError"])
def test_tool_or_unexpected_exception_is_not_an_acceptable_business_result(stored, kind):
    path, _ = stored
    result = inspect(path, requests=[request()],
                     results=[{"index": 0, "worker_index": 0, "ok": False,
                               "error": {"type": kind, "message": "observed"}}])
    assert result["consistent"] is False
    assert any("Unexpected operation exception" in violation for violation in result["violations"])


def test_known_business_error_and_absent_order_are_valid(stored):
    path, _ = stored
    result = inspect(path, requests=[request(quantity=11)],
                     results=[{"index": 0, "worker_index": 0, "ok": False,
                               "error": {"type": "InsufficientInventory"}}],
                     expected_orders={"first": None})
    assert result["consistent"] is True
    assert result["response_checks"]["failed"] == 1


@pytest.mark.parametrize("results", [[], [response(1, {})], [response(True, {})],
                                     [response(0, {}), response(0, {})]])
def test_missing_or_invalid_result_collections_cannot_pass(stored, results):
    path, _ = stored
    result = inspect(path, requests=[request()], results=results)
    assert result["consistent"] is False


def test_recovery_is_explicit_and_records_actual_file_fingerprints(stored):
    path, _ = stored
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = recover_episode_d_database(path, data_dir=path.parent, workers_stopped=True,
                                        expected_identity=(path.stat().st_dev, path.stat().st_ino))
    assert result["status"] == "NO_STORAGE_CHANGE", result
    assert result["before"]["database"]["sha256"] == before
    assert result["after"]["database"]["sha256"] == before
    assert result["integrity_check"] == ["ok"]
    assert result["error"] is None


def test_recovery_refuses_live_workers_and_wrong_identity(stored):
    path, _ = stored
    before = path.read_bytes()
    assert recover_episode_d_database(path, data_dir=path.parent,
                                      workers_stopped=False)["status"] == "ERROR"
    assert recover_episode_d_database(path, data_dir=path.parent, workers_stopped=True,
                                      expected_identity=(-1, -1))["status"] == "ERROR"
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "sidecar", "outside"])
def test_recovery_rejects_unsafe_storage_before_open(stored, tmp_path, kind):
    path, _ = stored
    before = path.read_bytes()
    allowed = tmp_path
    if kind == "symlink":
        alias = tmp_path / "alias.sqlite"
        alias.symlink_to(path)
        path = alias
    elif kind == "hardlink":
        alias = tmp_path / "alias.sqlite"
        os.link(path, alias)
        path = alias
    elif kind == "sidecar":
        (tmp_path / "business.sqlite-journal").symlink_to(path)
    else:
        allowed = tmp_path / "separate"
        allowed.mkdir()
    result = recover_episode_d_database(path, data_dir=allowed, workers_stopped=True)
    assert result["status"] == "ERROR"
    assert result["before"] is None
    assert (tmp_path / "business.sqlite").read_bytes() == before


def test_recovery_never_creates_missing_database(tmp_path):
    path = tmp_path / "missing.sqlite"
    result = recover_episode_d_database(path, data_dir=tmp_path, workers_stopped=True)
    assert result["status"] == "ERROR"
    assert not path.exists()


def test_real_killed_writer_hot_journal_is_recovered_before_read_only_oracle(stored):
    path, _ = stored
    # This is a trusted SQLite fixture writer, not an import of candidate code.
    # A small cache forces pending pages to disk and a real hot rollback journal.
    script = '''
import signal, sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute("PRAGMA foreign_keys = ON")
connection.execute("PRAGMA cache_size = 1")
connection.execute("BEGIN IMMEDIATE")
connection.executemany(
    "INSERT INTO orders(order_id, sku, quantity, status, reservation_state) "
    "VALUES (?, 'alpha', 1, 'created', 'none')",
    [("pending-" + str(index) + "x" * 2000,) for index in range(100)],
)
print("uncommitted-pages-written", flush=True)
signal.pause()
'''
    process = subprocess.Popen([sys.executable, "-I", "-c", script, str(path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([process.stdout], [], [], 5)[0], "fixture writer did not reach the stop point"
        assert process.stdout.readline().strip() == "uncommitted-pages-written"
        assert Path(str(path) + "-journal").exists()
        process.kill()
        assert process.wait(timeout=5) == -9
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
    recovery = recover_episode_d_database(path, data_dir=path.parent, workers_stopped=True)
    assert recovery["status"] == "RECOVERED", recovery
    assert recovery["before"]["-journal"] is not None
    assert recovery["after"]["-journal"] is None
    result = inspect(path, expected_order_ids=set())
    assert result["consistent"] is True, result["violations"]
    assert result["orders"] == result["ledger"] == []
