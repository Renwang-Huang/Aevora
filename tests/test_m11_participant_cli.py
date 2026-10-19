"""Incremental M1.1 contracts; these are not evidence of live model calls."""
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmark import cli
from benchmark.participant import build_participant, PARTICIPANT_INSTRUCTIONS
from benchmark.runner import BenchmarkRunner
from integrations.agents import ExecutionResult, ExecutionStatus


def test_single_and_multi_receive_identical_business_task_bytes(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    prepared = runner.prepare("D", "v01")
    source = tmp_path / "runs" / prepared["run_id"] / "workspace"
    single = build_participant(source, tmp_path / "single", agent_mode="single")
    multi = build_participant(source, tmp_path / "multi")
    for relative in ("ISSUE.md", "TASK.md", "public.json"):
        assert (single / relative).read_bytes() == (multi / relative).read_bytes()
    for directory in ("app", "tests/public"):
        first = {p.relative_to(single).as_posix(): p.read_bytes() for p in (single / directory).rglob("*.py")}
        second = {p.relative_to(multi).as_posix(): p.read_bytes() for p in (multi / directory).rglob("*.py")}
        assert first == second
    assert not (single / ".codex/agents").exists()
    assert "single-agent" in (single / "AGENTS.md").read_text()
    assert (multi / "AGENTS.md").read_text() == PARTICIPANT_INSTRUCTIONS
    assert len(list((multi / ".codex/agents").glob("*.toml"))) == 3


@pytest.mark.parametrize("mode", ["", "simulated", "../multi", None])
def test_participant_rejects_unknown_mode_before_writing(tmp_path, mode):
    with pytest.raises(ValueError, match="agent mode"):
        build_participant(tmp_path / "missing", tmp_path / "participant", agent_mode=mode)
    assert not (tmp_path / "participant").exists()


@pytest.mark.parametrize("reason", ["CANCELLED_BY_OPERATOR", "COLLECTOR_INTERRUPTED"])
def test_runner_preserves_cancellation_without_evaluation(tmp_path, monkeypatch, reason):
    import integrations.codex_agent as module
    seen = {}
    def execute(self, task, context):
        seen["workspace"] = Path(context.workspace)
        return ExecutionResult(ExecutionStatus.CANCELLED, None,
            errors=(reason,), runtime_metadata={"runtime_result": "CANCELLED",
                "failure_kind": reason, "agent_mode": "single", "completion_policy": "completion-aware"})
    monkeypatch.setattr(module.CodexAgentAdapter, "execute", execute)
    runner = BenchmarkRunner(tmp_path / "runs")
    report = runner.run_agent("D", config=SimpleNamespace(agent_mode="single", completion_policy="completion-aware"))
    assert report["overall_status"] == "CANCELLED"
    assert report["failure_kind"] == reason
    assert report["evaluation_status"] == "NOT_RUN"
    assert "EVALUATE" not in report["lifecycle"]
    assert report["environment_reset"] is True
    assert report["experience"]["status"] == "DISABLED"
    assert not (seen["workspace"] / ".codex/agents").exists()
    assert (tmp_path / "runs" / report["run_id"] / "run_evidence_manifest.json").is_file()


@pytest.mark.parametrize("options,expected", [
    ([], {"timeout_seconds": 900, "request_budget": 160, "completion_policy": "bounded", "agent_mode": "multi"}),
    (["--completion-policy", "completion-aware", "--agent-timeout", "none", "--request-budget", "none", "--agent-mode", "single"],
     {"timeout_seconds": None, "request_budget": None, "completion_policy": "completion-aware", "agent_mode": "single"}),
])
def test_cli_passes_explicit_policy_without_silent_conversion(tmp_path, monkeypatch, capsys, options, expected):
    import integrations.codex_agent as module
    seen = {}
    def configuration(**values):
        seen.update(values)
        return SimpleNamespace(**values)
    monkeypatch.setattr(module.CodexConfig, "from_environment", staticmethod(configuration))
    monkeypatch.setattr(BenchmarkRunner, "run_agent", lambda *a, **k: {"overall_status": "CANCELLED"})
    assert cli.main(["--runs-root", str(tmp_path), "run-codex", "--episode", "D", *options]) == 5
    assert {k: seen[k] for k in expected} == expected
    assert json.loads(capsys.readouterr().out)["overall_status"] == "CANCELLED"


@pytest.mark.parametrize("flag,value", [("--agent-timeout", "nan"), ("--agent-timeout", "inf"),
    ("--agent-timeout", "0"), ("--agent-timeout", "-1"), ("--request-budget", "0"),
    ("--request-budget", "1.5"), ("--request-budget", "-1")])
def test_cli_rejects_ambiguous_or_invalid_limits(flag, value):
    with pytest.raises(SystemExit) as error:
        cli.main(["run-codex", "--episode", "D", flag, value])
    assert error.value.code == 2


@pytest.mark.parametrize("action", ["status", "snapshot", "cancel"])
def test_runtime_control_rejects_noncanonical_run_reference(tmp_path, capsys, action):
    assert cli.main(["--runs-root", str(tmp_path), action, "--run-id", "../../other-run"]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "ERROR"


@pytest.mark.parametrize("action", ["status", "snapshot"])
@pytest.mark.parametrize("terminal", ["CANCELLED", "ERROR", "TIMEOUT"])
def test_control_read_succeeds_and_preserves_terminal_outcome(tmp_path, capsys, action, terminal):
    from integrations.runtime_control import RuntimeControl
    run_id = "27b75bf5-e88b-4b23-8fe6-dad78ebf3f25"
    run = tmp_path / run_id
    run.mkdir()
    control = RuntimeControl(run, run_id, completion_policy="completion-aware", agent_mode="single")
    control.finish(terminal, "SYNTHETIC_TERMINAL_CONTRACT")
    assert cli.main(["--runs-root", str(tmp_path), action, "--run-id", run_id]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == terminal
    assert result["control_query"]["source"] == "trusted_cli_observer"
