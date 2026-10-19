"""Offline synthetic fault contract, NOT Codex/model/multi-agent run evidence.

The Adapter, bubblewrap, process exit, patch extraction, raw exec parser, cgroup
and watchdog run normally. Only the model broker is a local inert Unix socket
and the executable is a tiny explicitly synthetic Python fixture. The poisoned
native session file invokes a real archive_native_rollouts refusal. No key or
model service is accessed. Optional alternate source is a proposal artifact,
never a mutation to production source; its executed source hash is recorded.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sys
import textwrap
import types

import pytest

from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from integrations.agents import ExecutionContext, TaskInput

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("ORDERFLOW_ARCHIVE_FAULT_SOURCE", str(REPO / "integrations/codex_agent.py")))
module = types.ModuleType("integrations.native_archive_fault_contract")
module.__file__ = str(REPO / "integrations/codex_agent.py")
sys.modules[module.__name__] = module
exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), module.__dict__)


class InertSocketBroker:
    secret_values = ()
    metadata = {"transport": "SYNTHETIC_INERT_UNIX_SOCKET_NO_MODEL_CALL"}

    def __init__(self, *args, socket_path, **kwargs):
        self.socket_path = socket_path

    def __enter__(self):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.socket_path))
        self.socket.listen(1)
        return self

    def __exit__(self, *args):
        self.socket.close()
        return False


class LegacyContractBroker:
    base_url = "http://127.0.0.1:1/v1"
    secret_values = ()
    metadata = {"transport": "SYNTHETIC_UNUSED_LEGACY_BROKER_NO_MODEL_CALL"}

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def run(tmp_path, monkeypatch, mode, provider="gateway", fail_exception=None):
    monkeypatch.setattr(module, "SecureModelBroker", InertSocketBroker)
    monkeypatch.setattr(module, "ModelBroker", LegacyContractBroker)
    if fail_exception:
        def fail(*args, **kwargs):
            raise fail_exception("synthetic native archive fault")
        monkeypatch.setattr(module, "archive_native_rollouts", fail)
    runner = BenchmarkRunner(tmp_path / "runs")
    prepared = runner.prepare("A")
    archive = Path(prepared["artifacts"]["workspace"]).parent
    workspace = build_participant(archive / "workspace", archive / "participant")
    fixture = tmp_path / "synthetic-cli"
    fixture.write_text("#!/usr/bin/python3.12\n" + textwrap.dedent(f"""
        import json,os,sys
        from pathlib import Path
        if '--version' in sys.argv:
            print('synthetic-native-archive-fault-fixture NOT_CODEX')
            sys.exit(0)
        sys.stdin.read()
        print(json.dumps({{'type':'thread.started','thread_id':'synthetic-parent'}}),flush=True)
        print(json.dumps({{'type':'turn.started'}}),flush=True)
        for i in range(2):
            child='synthetic-child-'+str(i)
            print(json.dumps({{'type':'item.completed','item':{{'type':'collab_tool_call',
                'id':'synthetic-spawn-'+str(i),'tool':'spawn_agent','status':'completed',
                'sender_thread_id':'synthetic-parent','receiver_thread_ids':[child],
                'prompt':'Synthetic distinct task '+str(i),
                'agents_states':{{child:{{'status':'completed','message':'Synthetic return '+str(i)}}}}}}}}),flush=True)
        source=Path('/workspace/app/service.py')
        source.write_text(source.read_text()+'\\n# Synthetic archival contract change, not a repair.\\n')
        if {mode!r}=='real_link_refusal':
            directory=Path(os.environ['CODEX_HOME'])/'sessions'
            directory.mkdir()
            (directory/'poison.jsonl').symlink_to('/not-exposed-and-not-read')
        print(json.dumps({{'type':'turn.completed','usage':{{'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}}}}),flush=True)
    """))
    fixture.chmod(0o700)
    helper = fixture.with_name("codex-code-mode-host")
    helper.write_text("#!/bin/sh\nexit 0\n")
    helper.chmod(0o700)
    config = module.CodexConfig(fixture, tmp_path / "unused-not-a-secret", model="gpt-5.6-terra",
        provider_id=provider, reasoning_effort="max", timeout_seconds=5)
    result = module.CodexAgentAdapter(config).execute(TaskInput("A", "1.0.0", "Synthetic public task"),
        ExecutionContext(archive.name, str(workspace), constraints={"archive": str(archive),
            "baseline": str(archive / "workspace")}))
    evidence = {"classification": "offline synthetic exception integration contract, not live agent proof",
        "source": str(SOURCE), "executed_source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
        "run_id": archive.name, "result_status": result.status.value,
        "runtime_result": result.runtime_metadata["runtime_result"],
        "multi_agent_result": result.runtime_metadata["multi_agent_result"],
        "exec_verified_count": result.runtime_metadata.get("trace_observations", {}).get("subagents", {}).get("verified_count"),
        "native_rollouts": result.runtime_metadata.get("native_rollouts"),
        "native_observations": result.runtime_metadata.get("native_rollout_observations", "MISSING"),
        "errors": result.errors, "archive": str(archive), "submission": result.submission.reference if result.submission else None}
    (tmp_path / "contract_result.json").write_text(json.dumps(evidence, indent=2)+"\n")
    assert result.runtime_metadata["exit_code"] == 0
    assert result.runtime_metadata["runtime_result"] == "PASS"
    assert result.status.value == "SUBMITTED" and result.submission is not None
    assert result.runtime_metadata["trace_observations"]["integrity"]["status"] == "COMPLETE"
    assert result.runtime_metadata["trace_observations"]["subagents"]["verified_count"] == 2
    assert (archive / "codex_events.jsonl").exists() and (archive / "agent_trace.jsonl").exists()
    return result.runtime_metadata


def test_actual_native_link_refusal_cannot_silently_fallback_to_multiagent_pass(tmp_path, monkeypatch):
    metadata = run(tmp_path, monkeypatch, "real_link_refusal")
    assert metadata["native_rollouts"]["availability"] == "UNAVAILABLE"
    assert metadata["native_rollouts"]["reason"] == "ValueError"
    assert any("Native rollout archive failed: ValueError" in error for error in metadata["errors"])
    assert metadata["multi_agent_result"] == "PARTIAL"
    assert metadata["native_rollout_observations"]["integrity"]["status"] == "INCOMPLETE"


@pytest.mark.parametrize("exception", [OSError, ValueError, RuntimeError])
def test_native_archive_exception_is_partial_without_erasing_exec_facts(tmp_path, monkeypatch, exception):
    metadata = run(tmp_path, monkeypatch, "empty", fail_exception=exception)
    assert metadata["native_rollouts"]["reason"] == exception.__name__
    assert metadata["multi_agent_result"] == "PARTIAL"
    assert metadata["native_rollout_observations"]["integrity"]["status"] == "INCOMPLETE"


def test_successful_empty_strict_collection_keeps_existing_partial_verdict(tmp_path, monkeypatch):
    metadata = run(tmp_path, monkeypatch, "empty")
    assert metadata["native_rollouts"]["availability"] == "UNAVAILABLE"
    assert metadata["native_rollouts"]["reason"] == "no official session files"
    assert metadata["multi_agent_result"] == "PARTIAL"


def test_legacy_exec_without_native_delegation_is_partial_in_g24_profile(tmp_path, monkeypatch):
    metadata = run(tmp_path, monkeypatch, "empty", provider="legacy")
    assert "native_rollouts" not in metadata
    assert metadata.get("delegation_verification") != "PASS"
    assert metadata["multi_agent_result"] == "PARTIAL"
