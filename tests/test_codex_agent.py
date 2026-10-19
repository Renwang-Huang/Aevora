"""Synthetic CLI fault contracts; these are NOT native Agent run evidence.

The fixture is an ordinary short Python program in the actual participant
bubblewrap boundary. It tests archival/process/submission integration only.
"""
import json
from pathlib import Path
import textwrap

import pytest

from benchmark.runner import BenchmarkRunner
from integrations.agents import ExecutionContext, TaskInput
from integrations.codex_agent import CodexAgentAdapter, CodexConfig, native_command


class ContractBroker:
    base_url = "http://127.0.0.1:1/v1"
    secret_values = ()
    metadata = {"transport": "SYNTHETIC_CONTRACT_FIXTURE"}

    def __init__(self, auth_path, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fixture_config(tmp_path, behavior="change", timeout=5):
    fixture = tmp_path / "synthetic-cli"
    fixture.write_text("#!/usr/bin/python3.12\n" + textwrap.dedent(f"""
        import json,sys,time
        from pathlib import Path
        if '--version' in sys.argv:
            print('synthetic-contract-fixture NOT_CODEX')
            sys.exit(0)
        sys.stdin.read()
        print(json.dumps({{'type':'thread.started','thread_id':'synthetic-contract-thread'}}),flush=True)
        print(json.dumps({{'type':'turn.started'}}),flush=True)
        behavior={behavior!r}
        if behavior=='timeout':
            time.sleep(60)
        if behavior=='exit':
            print(json.dumps({{'type':'turn.failed','error':{{'message':'synthetic failure'}}}}),flush=True)
            sys.exit(12)
        if behavior=='incomplete':
            sys.exit(0)
        if behavior=='invalid':
            Path('/workspace/app/evil.py').symlink_to('/outside')
        if behavior=='change':
            p=Path('/workspace/app/service.py')
            p.write_text(p.read_text()+'\\n# Synthetic archival contract change; does not repair the incident.\\n')
        print(json.dumps({{'type':'turn.completed','usage':{{'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}}}}),flush=True)
    """))
    fixture.chmod(0o700)
    return CodexConfig(fixture, tmp_path / "unused-auth", timeout_seconds=timeout)


def execute(tmp_path, monkeypatch, behavior, timeout=5):
    from benchmark.participant import build_participant
    monkeypatch.setattr("integrations.codex_agent.ModelBroker", ContractBroker)
    runner = BenchmarkRunner(tmp_path / "runs")
    prepared = runner.prepare("A")
    archive = Path(prepared["artifacts"]["workspace"]).parent
    participant = build_participant(archive / "workspace", archive / "participant")
    result = CodexAgentAdapter(fixture_config(tmp_path, behavior, timeout)).execute(
        TaskInput("A", "1.0.0", "Public incident"),
        ExecutionContext(archive.name, str(participant), constraints={
            "archive": str(archive), "baseline": str(archive / "workspace")}))
    return result, archive


@pytest.mark.parametrize("behavior,kind,status", [
    ("no_patch", "NO_PATCH", "ERROR"),
    ("invalid", "INVALID_SUBMISSION", "ERROR"),
    ("incomplete", "TRACE_INCOMPLETE", "ERROR"),
    ("exit", "CODEX_EXECUTION_FAILED", "ERROR"),
    ("timeout", "EXECUTION_TIMEOUT", "TIMEOUT"),
])
def test_failure_contracts_preserve_real_exit_and_archive(tmp_path, monkeypatch, behavior, kind, status):
    result, archive = execute(tmp_path, monkeypatch, behavior, timeout=0.2 if behavior == "timeout" else 5)
    assert result.status.value == status
    assert result.submission is None
    assert result.runtime_metadata["failure_kind"] == kind
    assert result.runtime_metadata["subagents"]["verified_count"] == 0
    assert (archive / "runtime_metadata.json").is_file()
    assert (archive / "codex_events.jsonl").is_file()
    assert (archive / "agent_trace.jsonl").is_file()
    assert not (archive / "codex_events.pending").exists()
    assert result.errors


def test_contract_diff_reaches_unchanged_hidden_evaluator_and_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("integrations.codex_agent.ModelBroker", ContractBroker)
    runner = BenchmarkRunner(tmp_path / "runs")
    report = runner.run_agent("A", config=fixture_config(tmp_path))
    # No repair or native collaboration occurred; do not call this a challenge.
    assert report["runtime_result"] == "PASS"
    assert report["evaluation_result"] == "FAIL"
    assert report["integration_result"] == "PASS"
    assert report["overall_status"] == "FAIL"
    assert report["test_results"]["collected"] == 14
    assert report["test_results"]["failed"] > 0
    assert report["agent"]["subagents"]["verified_count"] == 0
    directory = tmp_path / "runs" / report["run_id"]
    assert not (directory / "codex-state").exists()
    assert report["environment_reset"]
    assert report["submission"]["sha256"] == report["agent"]["submission_sha256"]
    assert json.loads((directory / "runtime_metadata.json").read_text())["evaluation_result"] == "FAIL"


def test_missing_codex_startup_is_reported_and_reset(tmp_path):
    runner = BenchmarkRunner(tmp_path / "runs")
    report = runner.run_agent("A", config=CodexConfig(tmp_path / "missing", tmp_path / "auth"))
    assert report["overall_status"] == "ERROR"
    assert report["evaluation_result"] == "NOT_RUN"
    assert report["runtime_result"] == "ERROR"
    assert report["environment_reset"]
    metadata = json.loads(Path(report["artifacts"]["runtime_metadata"]).read_text())
    assert metadata["failure_kind"] == "STARTUP_FAILED"


def test_bubblewrap_failure_has_no_unisolated_fallback(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("bubblewrap unavailable; contract failure")
    monkeypatch.setattr("integrations.codex_agent.participant_command", fail)
    result, archive = execute(tmp_path, monkeypatch, "change")
    assert result.status.value == "ERROR"
    assert result.submission is None
    assert result.runtime_metadata["exit_code"] is None
    assert (archive / "codex_events.jsonl").read_text() == ""


def test_state_cleanup_failure_is_archived_and_does_not_escape_runner(tmp_path, monkeypatch):
    import benchmark.runner as runner_module
    original = runner_module.shutil.rmtree
    def denied(path, *args, **kwargs):
        if Path(path).name == "codex-state":
            raise PermissionError("synthetic cleanup fault")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(runner_module.shutil, "rmtree", denied)
    report = BenchmarkRunner(tmp_path / "runs").run_agent(
        "A", config=CodexConfig(tmp_path / "missing", tmp_path / "auth"))
    assert report["agent_state_cleanup"] == "ERROR"
    assert report["integration_result"] == "ERROR"
    assert report["overall_status"] == "ERROR"
    archived = json.loads((tmp_path / "runs" / report["run_id"] / "evaluation_report.json").read_text())
    assert archived == report
    assert any("cleanup" in error for error in report["execution_errors"])


def test_native_argv_uses_fresh_session_and_no_identity_or_bypass(tmp_path):
    config = CodexConfig(tmp_path / "codex", tmp_path / "identity")
    command = native_command(config, "http://127.0.0.1:1/v1")
    assert command[1] == "exec"
    assert "--json" in command and "--ephemeral" in command
    assert "workspace-write" in command
    assert not any("danger" in x or "resume" == x or "fork" == x for x in command)
    assert str(config.auth_path) not in command
    assert 'approval_policy="never"' in command


def test_planned_episode_does_not_start_codex(tmp_path):
    report = BenchmarkRunner(tmp_path / "runs").run_agent(
        "B", config=CodexConfig(tmp_path / "missing", tmp_path / "auth"))
    assert report["overall_status"] == "NOT_IMPLEMENTED"
    assert report["agent"]["execution"] == "UNAVAILABLE"


def test_planned_cli_needs_no_runtime_credentials(tmp_path, monkeypatch, capsys):
    from benchmark.cli import main
    monkeypatch.delenv("ORDERFLOW_CODEX_BINARY", raising=False)
    monkeypatch.delenv("ORDERFLOW_CODEX_AUTH_PATH", raising=False)
    assert main(["--runs-root", str(tmp_path / "runs"), "run-codex", "--episode", "C"]) == 4
    assert json.loads(capsys.readouterr().out)["overall_status"] == "NOT_IMPLEMENTED"


@pytest.mark.parametrize("timeout", [0, -1, 7201])
def test_invalid_runtime_limit_rejected(tmp_path, timeout):
    with pytest.raises(ValueError):
        CodexConfig(tmp_path / "codex", tmp_path / "auth", timeout_seconds=timeout)
