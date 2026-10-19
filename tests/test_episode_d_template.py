"""D artifacts preserve business interfaces and use actual candidate processes."""

import ast
from pathlib import Path

import pytest

from benchmark.episodes.episode_d import (
    FIXTURE_VERSION, ROOT, STRATEGIES, build_episode_d_fixture, episode_d_patch,
    episode_d_reference_patch,
)
from benchmark.runner import apply_patch
from evaluator.oracle import inspect_database
from evaluator.rpc import BusinessRPC, RemoteBusinessError


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_d_fixture_preserves_schema_and_has_valid_python(tmp_path, strategy):
    workspace = build_episode_d_fixture(tmp_path / strategy, strategy=strategy)
    assert FIXTURE_VERSION == "1.0.0"
    assert workspace == tmp_path / strategy
    assert (workspace / "app/persistence.py").read_bytes() == (ROOT / "app/persistence.py").read_bytes()
    assert (workspace / "app/orders.py").read_bytes() == (ROOT / "app/orders.py").read_bytes()
    for source in (workspace / "app").rglob("*.py"):
        ast.parse(source.read_text())
    assert sorted(path.name for path in workspace.iterdir()) == ["app"]


def test_d_defect_is_local_coordination_and_stale_real_update(tmp_path):
    workspace = build_episode_d_fixture(tmp_path / "buggy")
    service = (workspace / "app/service.py").read_text()
    inventory = (workspace / "app/inventory.py").read_text()
    assert "threading.RLock()" in service
    assert 'checkpoint("inventory_read")' in service
    assert service.index("snapshot = self.get_inventory(sku)") < service.index(
        "with self.persistence.transaction() as connection:")
    assert '"UPDATE inventory SET available = ?, reserved = ? WHERE sku = ?"' in inventory
    assert 'self._record(connection, order, "reserve"' in inventory


@pytest.mark.parametrize("strategy", ["reference", "flock", "split-ledger"])
def test_d_patch_is_real_and_applies_to_exact_target(tmp_path, strategy):
    workspace = build_episode_d_fixture(tmp_path / "candidate")
    target = build_episode_d_fixture(tmp_path / "expected", strategy=strategy)
    patch = tmp_path / "submission.diff"
    patch.write_text(episode_d_patch(strategy))
    assert patch.stat().st_size > 0
    apply_patch(workspace, patch)
    for path in (target / "app").rglob("*.py"):
        assert (workspace / "app" / path.relative_to(target / "app")).read_bytes() == path.read_bytes()


def test_d_reference_patch_restores_repository_baseline(tmp_path):
    workspace = build_episode_d_fixture(tmp_path / "candidate")
    patch = tmp_path / "reference.diff"
    patch.write_text(episode_d_reference_patch())
    apply_patch(workspace, patch)
    for source in (ROOT / "app").rglob("*.py"):
        assert (workspace / "app" / source.relative_to(ROOT / "app")).read_bytes() == source.read_bytes()


@pytest.mark.parametrize("strategy", ["buggy", "local-lock-only"])
def test_local_lock_baseline_is_not_fabricated_as_empty_patch(strategy):
    with pytest.raises(ValueError, match="workspace"):
        episode_d_patch(strategy)


def test_bad1_names_same_actual_artifact_as_buggy(tmp_path):
    first = build_episode_d_fixture(tmp_path / "buggy")
    second = build_episode_d_fixture(tmp_path / "local-lock-only", strategy="local-lock-only")
    for source in (first / "app").rglob("*.py"):
        assert (second / "app" / source.relative_to(first / "app")).read_bytes() == source.read_bytes()


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_d_strategies_have_real_normal_single_worker_business_path(tmp_path, strategy):
    workspace = build_episode_d_fixture(tmp_path / "candidate", strategy=strategy)
    data = tmp_path / "data"
    rpc = BusinessRPC(workspace, data, tmp_path / "worker.log", response_timeout=15).start()
    try:
        rpc.call("initialize", stock={"alpha": 10, "beta": 7}, reset=True)
        created = rpc.call("create_order", order_id="purchase", sku="alpha", quantity=3)
        assert created["status"] == "reserved"
        assert rpc.call("create_order", order_id="purchase", sku="alpha", quantity=3) == created
        with pytest.raises(RemoteBusinessError) as conflict:
            rpc.call("create_order", order_id="purchase", sku="beta", quantity=3)
        assert conflict.value.kind == "OrderConflict"
        with pytest.raises(RemoteBusinessError) as insufficient:
            rpc.call("create_order", order_id="rejected", sku="alpha", quantity=8)
        assert insufficient.value.kind == "InsufficientInventory"
        rpc.call("create_order", order_id="unreserved", sku="beta", quantity=2, reserve=False)
        rpc.call("reserve_inventory", order_id="unreserved")
        rpc.call("cancel_order", order_id="purchase")
        rpc.call("cancel_order", order_id="purchase")
        rpc.call("release_inventory", order_id="purchase")
    finally:
        rpc.close()
    oracle = inspect_database(data / "business.sqlite", expected_stock={"alpha": 10, "beta": 7},
                              data_dir=data)
    assert oracle["consistent"] is True, oracle["violations"]
    assert {row["order_id"] for row in oracle["orders"]} == {"purchase", "unreserved"}
    assert len(oracle["ledger"]) == 3


def test_flock_alternate_covers_all_writer_apis_and_stable_lock(tmp_path):
    workspace = build_episode_d_fixture(tmp_path / "flock", strategy="flock")
    source = (workspace / "app/service.py").read_text()
    assert "fcntl.flock(lock.fileno(), fcntl.LOCK_EX)" in source
    assert '"initialize", "create_order", "reserve_inventory"' in source
    assert '"cancel_order", "release_inventory"' in source
    assert '.write.lock", "a+b"' in source
    assert ".unlink(" not in source


def test_split_ledger_failure_is_separate_commit_not_removed_accounting(tmp_path):
    workspace = build_episode_d_fixture(tmp_path / "split", strategy="split-ledger")
    source = (workspace / "app/service.py").read_text()
    assert "newly_reserved" in source
    assert "self.inventory.reserve(connection, order_id, record=False)" in source
    assert 'self.inventory._record(connection, order, "reserve"' in source
    inventory = (workspace / "app/inventory.py").read_text()
    assert "record: bool = True" in inventory
    assert '"WHERE sku = ? AND available >= ?"' in inventory


def test_d_rejects_unknown_variant_and_strategy_before_writing(tmp_path):
    with pytest.raises(ValueError, match="variant"):
        build_episode_d_fixture(tmp_path / "invalid", variant="v02")
    with pytest.raises(ValueError, match="strategy"):
        build_episode_d_fixture(tmp_path / "invalid", strategy="invented")
    assert not (tmp_path / "invalid").exists()
