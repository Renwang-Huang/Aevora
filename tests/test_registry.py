import json
from pathlib import Path
import subprocess
import pytest

from app.service import OrderFlow
from benchmark.manifest import ROOT, private_config
from benchmark.registry import EpisodeRegistration, get_episode, register_episode
from benchmark.runner import BenchmarkRunner
from benchmark.sandbox import runtime_python, sandbox_command
from evaluator.fingerprints import evaluation_fingerprints, file_sha256
from evaluator.runner import evaluate
from evaluator.suites import get_suite


def test_registered_episodes_have_independent_fixture_and_suite(tmp_path):
    smoke = get_episode("SMOKE-001")
    episode_a = get_episode("A")
    assert smoke.fixture_factory is not episode_a.fixture_factory
    assert smoke.suite_id != episode_a.suite_id
    assert get_suite(smoke.suite_id).path != get_suite(episode_a.suite_id).path
    smoke.build(tmp_path / "smoke")
    episode_a.build(tmp_path / "a")
    assert (tmp_path / "a/app/persistence.py").read_bytes() == (ROOT / "app/persistence.py").read_bytes()
    assert (tmp_path / "smoke/app/persistence.py").read_bytes() != (ROOT / "app/persistence.py").read_bytes()
    assert len(get_suite("smoke").expected_tests) == 8
    assert len(get_suite("episode_a").expected_tests) == 14


def test_registry_rejects_unknown_and_duplicate_without_smoke_fallback(tmp_path):
    with pytest.raises(ValueError, match="registered"):
        get_episode("B")
    with pytest.raises(ValueError, match="Duplicate"):
        register_episode(get_episode("A"))
    with pytest.raises(ValueError, match="Unknown"):
        get_episode("A").build(tmp_path, "not-a-variant")
    with pytest.raises(ValueError, match="Unregistered"):
        get_suite("not-a-suite")


def test_report_fingerprints_are_real_and_stable(tmp_path):
    runner = BenchmarkRunner(tmp_path)
    first = runner.prepare("A")
    second = runner.prepare("A", "v01")
    assert first["run_id"] != second["run_id"]
    assert first["scenario_variant"] == "v01"
    assert first["fingerprints"] == second["fingerprints"]
    evidence = first["fingerprints"]
    assert evidence["private_manifest_sha256"] == file_sha256(ROOT / "evaluator/private_manifests/A.json")
    assert evidence["test_suite"]["version"] == "1.0.0"
    for group in ("evaluator", "fixture", "test_suite"):
        assert evidence[group]["files"]
        for path, sha in evidence[group]["files"].items():
            assert file_sha256(ROOT / path) == sha


def test_expected_identity_set_cannot_be_replaced_by_same_size_suite(tmp_path):
    result = evaluate(tmp_path, tmp_path / "output", suite_id="smoke",
                      expected_tests=[f"invented-{i}" for i in range(8)])
    assert result["status"] == "ERROR"
    assert result["pytest_exit_code"] is None
    assert "Expected test identities" in result["errors"][0]


def test_episode_a_workspace_boundary_includes_other_runs(tmp_path):
    runner = BenchmarkRunner(tmp_path)
    report_a = runner.prepare("A")
    other = runner.prepare("SMOKE-001")
    candidate = tmp_path / report_a["run_id"] / "workspace"
    paths = [ROOT / "evaluator/hidden_tests", ROOT / "evaluator/reference_patches/A-v01.diff",
             ROOT / "evaluator/private_manifests/A.json", ROOT / "app/service.py",
             tmp_path / other["run_id"] / "evaluation_report.json"]
    probes = [str(p) for p in paths] + ["/proc/1/root" + str(paths[-1])]
    code = "from pathlib import Path; import json; print(json.dumps([Path(p).exists() for p in " + repr(probes) + "]))"
    process = subprocess.run(sandbox_command(candidate, [runtime_python(), "-I", "-c", code]),
                             text=True, capture_output=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == [False] * len(probes)
    assert not (candidate / "evaluator").exists()
    assert not (candidate / "benchmark").exists()
    assert OrderFlow(candidate / "business.sqlite").get_inventory("SKU-1")["available"] == 50


def test_cli_does_not_accept_episode_mix_or_unknown_variant(tmp_path):
    runner = BenchmarkRunner(tmp_path)
    prepared = runner.prepare("A")
    with pytest.raises(ValueError, match="do not match"):
        runner.evaluate("SMOKE-001", run_id=prepared["run_id"])
    with pytest.raises(ValueError, match="Variant"):
        runner.evaluate("A", run_id=prepared["run_id"], variant="default")
    with pytest.raises(ValueError, match="Unknown"):
        runner.prepare("A", "missing")


def test_prepared_run_cannot_pass_after_trusted_environment_changes(tmp_path, monkeypatch):
    import benchmark.runner as runner_module
    runner = BenchmarkRunner(tmp_path)
    prepared = runner.prepare("A")
    original = runner_module.evaluation_fingerprints
    def changed(*args):
        fingerprints = original(*args)
        fingerprints["evaluator"]["sha256"] = "0" * 64
        return fingerprints
    monkeypatch.setattr(runner_module, "evaluation_fingerprints", changed)
    result = runner.evaluate("A", run_id=prepared["run_id"])
    assert result["overall_status"] == "ERROR"
    assert result["test_results"] is None
    assert "changed after preparation" in result["execution_errors"][0]
