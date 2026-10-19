from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import pytest

from app.service import OrderFlow
from benchmark.manifest import ROOT, ScenarioManifest, load_manifest, private_config
from benchmark.runner import BenchmarkRunner, apply_patch, copy_app
from benchmark.sandbox import runtime_python, sandbox_command


@pytest.mark.parametrize("episode", ["A", "B", "C", "D"])
def test_planned_is_not_success(tmp_path, episode):
    # M1 semantic migration: D now has a registered implementation. The
    # original Phase 3.5 source and this test's identity remain archived.
    if episode in ("A", "D"):
        assert load_manifest(episode).status == "IMPLEMENTED"
        assert private_config(episode)["implemented"] is True
        result = BenchmarkRunner(tmp_path).prepare(episode)
        assert result["overall_status"] == "PREPARED"
        assert result["test_results"] is None
        return
    assert load_manifest(episode).status == "PLANNED"
    assert private_config(episode)["implemented"] is False
    runner = BenchmarkRunner(tmp_path)
    result = runner.evaluate(episode)
    assert result["overall_status"] == "NOT_IMPLEMENTED"
    assert result["test_results"] is None
    assert not (tmp_path / result["run_id"] / "workspace").exists()


@pytest.mark.parametrize("change", [
    {"status": "PASS"}, {"version": "next"}, {"id": "../private"},
    {"evaluation": {"implemented": False}}, {"initial_state": {"stock": {"SKU": True}}},
    {"runtime": {"python": "3.10", "database": "sqlite", "topology": "single"}},
])
def test_manifest_rejects_invalid(change):
    data = asdict(load_manifest("SMOKE-001"))
    data.update(change)
    with pytest.raises(ValueError):
        ScenarioManifest.from_dict(data)


def test_real_workspace_boundary(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    report = runner.prepare("SMOKE-001")
    assert report["overall_status"] == "PREPARED"
    workspace = tmp_path / "runs" / report["run_id"] / "workspace"
    assert not (workspace / "evaluator").exists()
    private = ROOT / "evaluator" / "hidden_tests"
    reference = ROOT / "evaluator" / "reference_patches" / "SMOKE-001.diff"
    canary = tmp_path / "private-canary"
    canary.write_text("PRIVATE")
    # Absolute paths, traversal, and /proc root access must all be denied by the OS boundary.
    probes = [str(private), str(reference), str(ROOT / "app"), str(canary),
              "/proc/1/root" + str(reference), "/workspace/../../" + str(canary).lstrip("/")]
    code = "from pathlib import Path; import json; print(json.dumps([Path(p).exists() for p in " + repr(probes) + "]))"
    completed = subprocess.run(sandbox_command(workspace, [runtime_python(), "-I", "-c", code]),
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == [False] * len(probes)
    public = subprocess.run(sandbox_command(workspace, [runtime_python(), "-m", "unittest", "discover", "-s", "tests/public"]),
                            capture_output=True, text=True)
    assert public.returncode == 0, public.stderr


def test_reset_restores_business_and_keeps_reports(tmp_path):
    runner = BenchmarkRunner(tmp_path)
    first = runner.prepare("SMOKE-001")
    second = runner.prepare("SMOKE-001")
    assert first["run_id"] != second["run_id"]
    db = tmp_path / first["run_id"] / "workspace" / "business.sqlite"
    flow = OrderFlow(db)
    flow.create_order("reset-me", "SKU-1", 3)
    assert flow.get_inventory("SKU-1")["available"] == 7
    result = runner.reset("SMOKE-001")
    assert first["run_id"] in result["run_ids"]
    assert flow.get_inventory("SKU-1")["available"] == 10
    assert flow.audit()["orders"] == []
    assert runner.report(first["run_id"])["run_id"] == first["run_id"]


def test_submission_links_and_patch_escape_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "service.py").symlink_to(ROOT / "app" / "service.py")
    with pytest.raises(ValueError, match="symlinks"):
        copy_app(source, tmp_path / "candidate")
    patch = tmp_path / "evil.diff"
    patch.write_text("--- a/app/../../private.py\n+++ b/app/../../private.py\n@@ -1 +1 @@\n-a\n+b\n")
    with pytest.raises(ValueError, match="only Python"):
        apply_patch(tmp_path, patch)


def test_submission_error_is_archived(tmp_path):
    runner = BenchmarkRunner(tmp_path)
    result = runner.evaluate("SMOKE-001", tmp_path / "missing.diff")
    assert result["overall_status"] == "ERROR"
    assert result["execution_errors"]
    assert runner.report(result["run_id"])["overall_status"] == "ERROR"
    assert result["experience"]["status"] == "DISABLED"
    assert result["agent"]["execution"] == "UNAVAILABLE"


def test_reset_does_not_follow_agent_database_links(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    prepared = runner.prepare("SMOKE-001")
    external = tmp_path / "private.sqlite"
    protected = OrderFlow(external)
    protected.initialize({"PRIVATE": 41})
    before = external.read_bytes()
    db = tmp_path / "runs" / prepared["run_id"] / "workspace" / "business.sqlite"
    db.unlink()
    db.symlink_to(external)
    (db.parent / "business.sqlite-wal").symlink_to(external)
    runner.reset("SMOKE-001")
    assert external.read_bytes() == before
    assert not db.is_symlink()
    assert OrderFlow(db).get_inventory("SKU-1")["available"] == 10


def test_reset_failure_is_archived_instead_of_stale_prepared(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    prepared = runner.prepare("SMOKE-001")
    directory = tmp_path / "runs" / prepared["run_id"]
    import shutil
    shutil.rmtree(directory / "workspace")
    outside = tmp_path / "outside"
    outside.mkdir()
    (directory / "workspace").symlink_to(outside, target_is_directory=True)
    result = runner.evaluate("SMOKE-001", tmp_path / "missing.diff", run_id=prepared["run_id"])
    assert result["overall_status"] == "ERROR"
    assert result["environment_reset"] is False
    assert any("reset failed" in error for error in result["execution_errors"])
    assert runner.report(prepared["run_id"])["overall_status"] == "ERROR"
