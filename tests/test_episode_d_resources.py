import json
from pathlib import Path
import os

from benchmark.episodes.episode_d import build_episode_d_fixture
from evaluator.resource_recovery import recover_worker_scopes
from evaluator.runner import evaluate


def test_owned_scope_recovery_rejects_paths_outside_delegation(tmp_path):
    file = tmp_path / "pool-resource-invalid.json"
    file.write_text(json.dumps({"source":"trusted_worker_supervisor", "owner_uid":os.getuid(),
                               "cgroup_path":"/tmp/orderflow-00000000-0000-0000-0000-000000000000"}))
    rows = recover_worker_scopes(tmp_path)
    assert len(rows)==1
    assert rows[0]["availability"]=="UNAVAILABLE"
    assert not rows[0]["cleanup_complete"]


def test_owned_scope_recovery_rejects_linked_receipt(tmp_path):
    outside=tmp_path/"unrelated.json"
    outside.write_text("{}")
    (tmp_path/"pool-resource-invalid.json").symlink_to(outside)
    rows=recover_worker_scopes(tmp_path)
    assert rows[0]["availability"]=="UNAVAILABLE"
    assert outside.read_text()=="{}"


def test_evaluator_does_not_erase_unverified_prior_pool_receipt(tmp_path):
    workspace=build_episode_d_fixture(tmp_path/"workspace",strategy="reference")
    artifacts=tmp_path/"artifacts"
    artifacts.mkdir()
    receipt=artifacts/"pool-resource-unverified.json"
    receipt.write_text('{"source":"untrusted"}')
    before=receipt.read_bytes()
    result=evaluate(workspace,artifacts,suite_id="episode_d")
    assert result["status"]=="ERROR"
    assert result["pytest_exit_code"] is None
    assert receipt.read_bytes()==before
    assert any("refusing artifact reuse" in e for e in result["errors"])


def test_d_timeout_reaps_real_worker_pool_and_control_socket(tmp_path):
    workspace=build_episode_d_fixture(tmp_path/"workspace",strategy="reference")
    (workspace/"app/service.py").write_text("while True:\n    pass\n")
    artifacts=tmp_path/"artifacts"
    result=evaluate(workspace,artifacts,timeout_seconds=2,suite_id="episode_d")
    assert result["status"]=="TIMEOUT", result
    assert result["pytest_exit_code"]==-9
    receipts=list(artifacts.glob("pool-resource-*.json"))
    assert receipts, "Timeout must occur after a real controlled pool starts"
    cleanup=json.loads((artifacts/"recovery-owned-pool-resources.json").read_text())
    assert all(row["cleanup_complete"] and row.get("control_directory_removed") for row in cleanup),cleanup
    assert all(not Path(json.loads(p.read_text())["cgroup_path"]).exists() for p in receipts)
