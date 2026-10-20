"""One non-scored DeepSeek native adapter smoke; never pooled with Pilot/Formal."""
from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from audit import E, now, write
from benchmark.runner import BenchmarkRunner
from integrations.codex_agent import CodexConfig


SMOKE_BOOTSTRAP = E / "02_calibration/smoke_world_v2/SMOKE_BOOTSTRAP.json"


def main() -> int:
    if not SMOKE_BOOTSTRAP.is_file():
        raise SystemExit("SMOKE_BOOTSTRAP_MISSING")
    agent_mode = os.environ.get("AEVORA_G24_AGENT_MODE", "single")
    native_child_task = """# Native child task

You are the one direct native child for this non-scored SMOKE-001 adapter run.
Run exactly one actual read-only verification command:

`python3 -m unittest discover -s tests/public -v`

Then return the literal `CHILD_OK`, the command, and its exact exit result.
Do not read or edit other files. Do not call spawn_agent, send_message,
followup_task, or any other delegation tool. Do not spawn or contact any
other agent. Return directly to the lead.
"""
    child_instruction = (
        "This run validates the native parent/child identity path. Use exactly one real native "
        "child agent for independent investigation. Call spawn_agent with fork_turns='none', then "
        "call send_message to that child path with the same task text; never use fork_turns='all'. "
        "Tell the child to read /workspace/CHILD_TASK.md; that file contains its read-only task. "
        "Do not spawn more; the child must return directly and must not spawn its own agents. "
        "Wait for the child terminal result, then implement and test the repair yourself."
        if agent_mode == "multi" else
        "This run validates the single-agent functional path. Do not spawn child agents. "
        "Implement and test the repair yourself."
    )
    os.environ["AEVORA_G24_SMOKE_INSTRUCTION"] = (
        "This is a non-scored adapter compatibility smoke. Do not claim a benchmark result. "
        "Before implementation, call resolve_experience with task_context={}. Follow every "
        "next_cursor until has_more=false if the response is paged. Call build_evidence_bundle "
        "with the actual returned experience_id and query_id, following all continuation pages. "
        "Call record_decision using the actual recommendation_id and choose VERIFY with concrete "
        "verification steps. During final review, call propose_experience once with the actual "
        "current-run Query and Decision IDs, explicit conditions and limitations; it remains "
        "UNTRUSTED. " + child_instruction
    )
    config = CodexConfig.from_environment(
        model="deepseek-flash",
        timeout_seconds=None,
        provider_id="gateway",
        reasoning_effort="max",
        request_budget=None,
        completion_policy="completion-aware",
        agent_mode=agent_mode,
        stream_idle_timeout_ms=3_600_000,
        connect_timeout_seconds=30,
        experience_mode="aevora",
        enable_experience_proposals=True,
        experience_protocol_profile="aevora.mcp/2.0.0-rc2",
        experience_v2_bootstrap_path=SMOKE_BOOTSTRAP,
        agent_protocol=os.environ.get("AEVORA_G24_AGENT_PROTOCOL", "v1"),
        max_agent_threads=2 if agent_mode == "multi" else 1,
        max_child_agents=1 if agent_mode == "multi" else 0,
        required_verified_children=1 if agent_mode == "multi" else 0,
        native_child_task=native_child_task if agent_mode == "multi" else None,
    )
    label = "smoke-" + uuid.uuid4().hex
    runs = E / "09_evidence/smoke_runs"
    result = BenchmarkRunner(runs).run_agent(
        "SMOKE-001",
        config=config,
        evaluation_timeout=None,
    )
    summary = {
        "status": "SUBMITTED" if result.get("overall_status") in ("PASS", "FAIL") else "BLOCKED",
        "created": now(),
        "smoke_label": label,
        "run_id": result.get("run_id"),
        "overall_status": result.get("overall_status"),
        "runtime_result": result.get("runtime_result"),
        "integration_result": result.get("integration_result"),
        "evaluation_result": result.get("evaluation_result"),
        "agent_mode": result.get("agent_mode"),
        "provider": result.get("provider"),
        "failure_kind": result.get("failure_kind"),
        "execution_errors": result.get("execution_errors", []),
        "experience": result.get("experience"),
        "agent": result.get("agent"),
        "pooled_with_pilot": False,
        "pooled_with_formal": False,
    }
    write(E / "09_evidence/ADAPTER_SMOKE_RESULT.json", summary)
    print(json.dumps({"status": summary["status"], "run_id": summary["run_id"],
                      "overall_status": summary["overall_status"],
                      "failure_kind": summary["failure_kind"]}, sort_keys=True))
    return 0 if summary["status"] == "SUBMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
