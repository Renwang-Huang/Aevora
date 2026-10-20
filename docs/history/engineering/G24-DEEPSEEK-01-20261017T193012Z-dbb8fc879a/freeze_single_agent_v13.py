"""Freeze the append-only G24 v1.3 Single-Agent Pilot candidate.

This is a runtime-profile revision only. It preserves v1.2, the formal task
manifest, the balanced formal order, and the 20261018 seed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from audit import E, sha, write


def main() -> int:
    v12_path = E / "01_protocol/PRE_REGISTERED_PROTOCOL_v1.2.json"
    tasks_path = E / "01_protocol/TASKS_FROZEN_v1.2.json"
    manifest_path = E / "01_protocol/EPISODE_MANIFEST_v1.2.csv"
    order_path = E / "01_protocol/FORMAL_ARM_ORDER.json"
    v12 = json.loads(v12_path.read_text())
    tasks = json.loads(tasks_path.read_text())
    order = json.loads(order_path.read_text())
    smoke = json.loads(
        (E / "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json").read_text()
    )
    d35 = json.loads(
        (E / "09_evidence/NATIVE_ADAPTER_SMOKE_RECEIPT.json").read_text()
    )
    native_gate = json.loads((E / "09_evidence/G24_D3_5_GATE.json").read_text())
    fairness = json.loads(
        (E / "01_protocol/memory/FAIRNESS_RECEIPT.json").read_text()
    )
    oracle_ref = json.loads((E / "09_evidence/ORACLE_REFERENCE_PROBE.json").read_text())
    pagination = json.loads((E / "09_evidence/PAGINATION_RESULT.json").read_text())
    source_commit = subprocess.check_output(
        ["git", "-C", str(E / "worktree"), "rev-parse", "HEAD"], text=True
    ).strip()
    source_tree = subprocess.check_output(
        ["git", "-C", str(E / "worktree"), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    if smoke.get("agent_mode") != "single" or smoke.get("runtime_result") != "PASS":
        raise SystemExit("SINGLE_AGENT_SMOKE_NOT_AVAILABLE")
    if d35.get("status") != "CONDITIONAL":
        raise SystemExit("D3_5_RECEIPT_NOT_CONDITIONAL")
    if native_gate.get("status") != "CONDITIONAL":
        raise SystemExit("D3_5_GATE_NOT_CONDITIONAL")

    tasks13 = E / "01_protocol/TASKS_FROZEN_v1.3.json"
    manifest13 = E / "01_protocol/EPISODE_MANIFEST_v1.3.csv"
    order13 = E / "01_protocol/FORMAL_ARM_ORDER_v1.3.json"
    shutil.copy2(tasks_path, tasks13)
    shutil.copy2(manifest_path, manifest13)
    shutil.copy2(order_path, order13)

    frozen_at = datetime.now(timezone.utc).isoformat()
    v13 = {
        "schema": "aevora.g24.preregistered.protocol/1.3",
        "version": "1.3",
        "status": "SINGLE_AGENT_PILOT_READY_FOR_APPROVAL",
        "frozen_at": frozen_at,
        "generation": "G24_DEEPSEEK_01",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "taskbook": v12.get("taskbook"),
        "taskbook_sha256": v12.get("taskbook_sha256"),
        "previous_version": {
            "version": "1.2",
            "protocol_sha256": sha(v12_path),
            "tasks_sha256": sha(tasks_path),
            "preserved_and_not_rewritten": True,
        },
        "runtime_revision_reason": {
            "code": "NATIVE_DEPTH_ENFORCEMENT_UNAVAILABLE",
            "evidence": "Codex CLI 0.163.0 exposes max_concurrent_threads_per_session but no child depth or per-child filesystem-permission setting; the actual D3.5 run created a depth-2 descendant despite a child budget of one.",
            "native_adapter_receipt": sha(E / "09_evidence/NATIVE_ADAPTER_SMOKE_RECEIPT.json"),
            "native_gate_receipt": sha(E / "09_evidence/G24_D3_5_GATE.json"),
        },
        "runtime": {
            "profile_id": "G24_DEEPSEEK_01_SINGLE_AGENT",
            "provider": "deepseek",
            "authorized_endpoint": "api.deepseek.com",
            "requested_model": "deepseek-flash",
            "effective_model": smoke.get("provider", {}).get("effective_model", "deepseek-flash"),
            "reasoning_effort": "max",
            "codex_cli": "0.163.0",
            "agent_mode": "single",
            "agent_protocol": "v1",
            "runtime_class": "ADAPTED_RUNTIME",
            "native_parent_child_claimed": False,
            "native_parent_child_status": "NOT_APPLICABLE_SINGLE_AGENT",
            "native_depth_enforcement": "UNAVAILABLE",
            "child_read_only_enforcement": "UNAVAILABLE",
            "request_budget": None,
            "completion_policy": "completion-aware",
            "total_wall_clock_cap": None,
            "all_arms_same_runtime": True,
            "max_child_agents": 0,
        },
        "runtime_gate": {
            "single_agent_functional_smoke": "PASS",
            "single_agent_smoke_run": smoke.get("run_id"),
            "single_agent_public_tests": "PASS_4_OF_4",
            "single_agent_model_oracle_result": smoke.get("evaluation_result", "FAIL"),
            "mcp_four_tools": "PASS",
            "mcp_pagination": "PASS",
            "trusted_reference_oracle_probe": oracle_ref.get("status"),
            "independent_oracle_execution": "PASS",
            "oracle_boundary": "VERIFIED",
            "native_adapter_smoke": "CONDITIONAL",
            "native_depth_enforcement": "UNAVAILABLE",
            "child_read_only_enforcement": "UNAVAILABLE",
            "pilot_readiness": "READY_FOR_APPROVAL",
            "pilot_requires_explicit_user_approval": True,
            "formal_execution": "BLOCKED_PENDING_USER_APPROVAL",
        },
        "arms": v12.get("arms"),
        "design": {
            **v12.get("design", {}),
            "runtime_scope": "SINGLE_AGENT_ALL_ARMS",
            "all_arms_same_model_runtime": True,
            "native_delegation": "DISABLED",
            "formal_arm_order": order.get("blocks"),
            "formal_arm_order_sha256": sha(order_path),
            "formal_arm_order_seed": order.get("seed"),
            "arm_order_position_counts": order.get("position_counts"),
            "arm_order_balanced": order.get("balanced"),
            "pilot_blocks": ["P01", "P02"],
            "formal_minimum_runs": 24,
            "formal_target_runs": 24,
            "formal_expansion_after_start": "FORBIDDEN",
            "fresh_session_per_run": True,
            "paired_block_unit": True,
            "negative_transfer_formal_blocks": ["F03", "F04", "F05"],
            "negative_transfer_inference": "EXPLORATORY_ONLY_3_FORMAL_BLOCKS",
        },
        "primary_endpoints": v12.get("primary_endpoints"),
        "failure_and_replacement": v12.get("failure_and_replacement"),
        "statistics": v12.get("statistics"),
        "calibration": {
            **v12.get("calibration", {}),
            "calibration_rerun": False,
        },
        "fairness": {
            **v12.get("fairness", {}),
            "same_source_experience": True,
            "same_scope_and_version": True,
            "same_historical_counterexamples": True,
            "same_tool_interaction_opportunity": "INTERFACE_ASYMMETRY_DECLARED; GRAPH USES FOUR AEVORA MCP TOOLS, RAW USES READ-ONLY TEXT",
            "receipt_sha256": sha(E / "01_protocol/memory/FAIRNESS_RECEIPT.json"),
        },
        "evidence": {
            "single_agent_smoke_result_sha256": sha(E / "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json"),
            "pagination_result_sha256": sha(E / "09_evidence/PAGINATION_RESULT.json"),
            "native_adapter_smoke_receipt_sha256": sha(E / "09_evidence/NATIVE_ADAPTER_SMOKE_RECEIPT.json"),
            "native_gate_receipt_sha256": sha(E / "09_evidence/G24_D3_5_GATE.json"),
            "oracle_reference_probe_sha256": sha(E / "09_evidence/ORACLE_REFERENCE_PROBE.json"),
            "fairness_receipt_sha256": sha(E / "01_protocol/memory/FAIRNESS_RECEIPT.json"),
            "formal_arm_order_sha256": sha(order_path),
            "native_depth_enforcement": "UNAVAILABLE",
            "native_parent_child": "NOT_CLAIMED",
        },
        "contracts": {
            "inherited_regression_count": 2109,
            "inherited_contract_count": 86,
            "historical_g23_outcomes_not_pooled": True,
            "native_multi_agent_proof_not_replaced_by_single_agent": True,
        },
        "pilot": {
            "status": "NOT_RUN",
            "readiness": "READY_FOR_APPROVAL",
            "requires_user_approval": True,
            "reason": "The single-agent adapter smoke has actual model calls, four MCP tools, patch extraction, public tests, pagination, and independent Oracle execution. Native depth/read-only enforcement is unavailable and is not claimed.",
        },
        "formal": "NOT_RUN",
        "prohibitions": sorted(set(v12.get("prohibitions", []) + [
            "NO_SINGLE_AGENT_RESULT_PRESENTED_AS_NATIVE_MULTI_AGENT",
            "NO_NATIVE_CLAIM_WHEN_DEPTH_ENFORCEMENT_UNAVAILABLE",
            "NO_PILOT_BEFORE_USER_APPROVAL",
        ])),
    }
    v13_path = E / "01_protocol/PRE_REGISTERED_PROTOCOL_v1.3.json"
    write(v13_path, v13)
    (E / "01_protocol/PRE_REGISTRATION_v1.3.md").write_text(
        f"""# G24 DeepSeek Single-Agent Pilot Protocol v1.3

**Status:** `SINGLE_AGENT_PILOT_READY_FOR_APPROVAL`  
**Frozen at:** `{frozen_at}`  
**Source:** `{source_commit}` / `{source_tree}`

v1.2 is preserved. This revision changes only the experimental runtime
candidate after the D3.5 native boundary investigation.

## Runtime

`G24_DEEPSEEK_01_SINGLE_AGENT`, `deepseek-flash`, reasoning `max`, Codex CLI
`0.163.0`, `agent_mode=single`. This is an adapted runtime. It is not a
Native Multi-Agent proof and cannot be pooled with G23 Terra results.

The native path remains unavailable for enforced depth-1/read-only delegation:
the CLI exposes thread concurrency limits but no child-depth or per-child
write-permission setting, and the actual D3.5 execution produced a depth-2
descendant. No further prompt-only retry is authorized.

## Preserved design

The formal task manifest, eight-block order, seed `20261018`, calibration
gate, ITT denominator, negative-transfer definition, and fairness snapshot
are preserved. All three arms use the same model and single-agent runtime.
Pilot P01/P02 remains unexecuted and requires explicit user approval.

## Evidence

- Single-agent adapter smoke: `{smoke.get("run_id")}`, public tests 4/4,
  Oracle `{smoke.get("evaluation_result", "FAIL")}` (retained as a real result).
- Pagination: `{pagination.get("status")}`.
- Trusted reference Oracle probe: `{oracle_ref.get("status")}`.
- Native boundary audit: `NATIVE_DEPTH_ENFORCEMENT_UNAVAILABLE`.
""",
        encoding="utf-8",
    )
    (E / "01_protocol/EXPERIMENT_PROTOCOL_CHANGELOG_v1.3.md").write_text(
        f"""# G24 Protocol Changelog v1.3

## v1.3 — Single-Agent Pilot candidate

Preserved v1.2 protocol `{sha(v12_path)}` and task manifest
`{sha(tasks_path)}` without rewriting them.

Changed runtime only:

- selected `G24_DEEPSEEK_01_SINGLE_AGENT`, `deepseek-flash`, effort `max`;
- set `agent_mode=single`, no child agents, no native Parent/Child claim;
- recorded `NATIVE_DEPTH_ENFORCEMENT_UNAVAILABLE` and
  `CHILD_READ_ONLY_ENFORCEMENT_UNAVAILABLE`;
- preserved formal order, seed `20261018`, and all 8 blocks;
- marked Pilot as `NOT_RUN`, `READY_FOR_APPROVAL`, requiring user approval.

The actual single-agent smoke is an adapted runtime result. It is not a
Multi-Agent result, not a Terra result, and not a new benchmark success.
""",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS",
        "protocol_sha256": sha(v13_path),
        "tasks_sha256": sha(tasks13),
        "manifest_sha256": sha(manifest13),
        "formal_order_sha256": sha(order13),
        "single_agent_smoke": smoke.get("run_id"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
