from dataclasses import asdict
import json

from benchmark.manifest import ROOT, load_manifest, private_config
from benchmark.registry import get_episode
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from evaluator.suites import get_suite


def test_episode_d_independent_registration():
    manifest, private = load_manifest("D"), private_config("D")
    registration = get_episode("D")
    assert manifest.status == "IMPLEMENTED"
    assert manifest.version == "2.0.0"
    assert registration.execution_strategy == "shared-db-workers"
    assert private["suite"] == "episode_d"
    assert get_suite(private["suite"]).path != get_suite("episode_a").path
    assert private["expected_test_count"] == len(private["expected_tests"])
    assert private["expected_test_count"] > 0
    assert "Negative Transfer" not in json.dumps(asdict(manifest))


def test_episode_d_prepare_and_reset_do_not_mix_scenes(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    reports = [runner.prepare(e) for e in ("SMOKE-001", "A", "D")]
    assert len({r["run_id"] for r in reports}) == 3
    for report in reports:
        assert report["overall_status"] == "PREPARED"
        assert report["test_results"] is None
        workspace = tmp_path / "runs" / report["run_id"] / "workspace"
        names = {p.name for p in (workspace / "tests/public").glob("*.py")}
        assert names == {p.name for p in get_episode(report["episode_id"]).public_tests}
    reset = runner.reset("D")
    assert reset["run_ids"] == [reports[-1]["run_id"]]
    assert runner.report(reports[0]["run_id"])["episode_id"] == "SMOKE-001"
    for episode in ("B", "C"):
        assert runner.evaluate(episode)["overall_status"] == "NOT_IMPLEMENTED"
