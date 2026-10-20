"""Freeze G24 analysis rules after task calibration and fairness checks."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from audit import E, sha, write
from benchmark.manifest import load_manifest


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    tasks_path = E / "01_protocol/TASKS_DRAFT.json"
    tasks = json.loads(tasks_path.read_text())
    calibration = json.loads((E / "02_calibration/attempt2/GATE.json").read_text())
    fairness = json.loads((E / "01_protocol/memory/FAIRNESS_RECEIPT.json").read_text())
    if calibration["status"] != "PASS":
        raise SystemExit("CALIBRATION_NOT_PASS")
    if not fairness["status"].startswith("INFORMATION_BALANCED"):
        raise SystemExit("FAIRNESS_NOT_BALANCED")
    formal = [item for item in tasks if item["stage"] == "FORMAL"]
    pilot = [item for item in tasks if item["stage"] == "PILOT"]
    if len(formal) != 8 or len(pilot) != 2:
        raise SystemExit("UNEXPECTED_BLOCK_COUNT")
    order_balance = json.loads((E / "01_protocol/ARM_ORDER_BALANCE.json").read_text())
    if not order_balance["balanced"]:
        raise SystemExit("ARM_ORDER_NOT_BALANCED")
    smoke_path = E / "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json"
    if not smoke_path.is_file():
        raise SystemExit("SMOKE_RESULT_MISSING")
    smoke = json.loads(smoke_path.read_text())
    pagination_path = E / "09_evidence/PAGINATION_RESULT.json"
    oracle_reference_path = E / "09_evidence/ORACLE_REFERENCE_PROBE.json"
    if not pagination_path.is_file() or not oracle_reference_path.is_file():
        raise SystemExit("PAGINATION_OR_REFERENCE_EVIDENCE_MISSING")
    pagination = json.loads(pagination_path.read_text())
    oracle_reference = json.loads(oracle_reference_path.read_text())
    frozen_at = datetime.now(timezone.utc).isoformat()
    runtime = {
        "profile_id": "G24_DEEPSEEK_01_SINGLE_AGENT",
        "provider": "deepseek",
        "requested_model": "deepseek-flash",
        "effective_model": smoke.get("provider", {}).get("effective_model", "UNVERIFIED"),
        "reasoning_effort": "max",
        "codex_cli": "0.163.0",
        "agent_mode": "single",
        "agent_protocol": "v1",
        "runtime_class": "ADAPTED_RUNTIME",
        "native_parent_child_claimed": False,
        "native_parent_child_status": "NOT_VERIFIED",
        "request_budget": None,
        "completion_policy": "completion-aware",
        "total_wall_clock_cap": None,
        "authorized_endpoint": "api.deepseek.com",
    }
    protocol = {
        "schema": "aevora.g24.preregistered.protocol/1.0",
        "status": "FROZEN_ANALYSIS_PROTOCOL_RUNTIME_REVIEW_REQUIRED",
        "frozen_at": frozen_at,
        "generation": "G24_DEEPSEEK_01",
        "baseline_commit": "a4d1450139cfcaff3c0c278e2476b07b532aa44d",
        "baseline_tree": "68fdf6d3b045040d2b52d181e05cf84d7f36ce9e",
        "taskbook": "G24-A v1.1",
        "taskbook_sha256": "5cf2946329f0254ce5370a72719e747f65496b26bcba29aa7bfcf431ee62f176",
        "runtime": runtime,
        "runtime_gate": {
            "functional_smoke": "PASS",
            "model_route": "PASS",
            "code_modification": "PASS",
            "public_tests": "PASS",
            "mcp_four_tools": "PASS",
            "mcp_pagination": pagination["status"],
            "independent_oracle_execution": "PASS",
            "smoke_oracle_result": smoke.get("evaluation_result", "FAIL"),
            "smoke_oracle_is_not_primary_benchmark_result": True,
            "trusted_reference_oracle_probe": oracle_reference["status"],
            "native_parent_child": "NOT_VERIFIED",
            "formal_execution": "BLOCKED_BY_RUNTIME_REVIEW",
        },
        "arms": [
            {
                "name": "GRAPH",
                "history": "REAL_FALKORDB_TRUSTED_WITNESS",
                "memory_interface": "Aevora MCP four tools",
                "graph_snapshot_sha256": fairness["graph_snapshot_sha256"],
            },
            {
                "name": "RAW_MEMORY",
                "history": "SAME_WITNESS_AS_TEXT",
                "memory_interface": "READ_ONLY_RAW_MEMORY_MD_THROUGH_PARTICIPANT_SHELL",
                "raw_memory_sha256": fairness["raw_memory_sha256"],
            },
            {
                "name": "NO_MEMORY",
                "history": "NONE",
                "memory_interface": "NONE",
            },
        ],
        "design": {
            "pilot_blocks": [item["block"] for item in pilot],
            "formal_blocks": [item["block"] for item in formal],
            "formal_minimum_runs": 24,
            "formal_target_runs": 24,
            "expansion_after_formal_start": "FORBIDDEN",
            "arm_order_seed": order_balance["seed"],
            "arm_order_position_counts": order_balance["position_counts"],
            "arm_order_balanced": True,
            "paired_block_unit": True,
            "fresh_session_per_run": True,
        },
        "primary_endpoints": {
            "negative_transfer_action_rate": {
                "numerator": "runs with actual patch materially adopting the invalid experience mechanism",
                "denominator": "all planned NEGATIVE_TRANSFER runs",
                "no_patch_rule": "NO_PATCH has no adopted invalid mechanism, contributes 0 to numerator, and is reported separately as NEGATIVE_TRANSFER_NOT_EVALUABLE",
                "classification_source": "INDEPENDENT_HOST_PATCH_REVIEW",
            },
            "independent_oracle_task_success": {
                "numerator": "original independent Oracle PASS",
                "denominator": "all planned formal runs",
                "itt": True,
                "error_classes": [
                    "ORACLE_FAIL",
                    "ERROR",
                    "TIMEOUT",
                    "NO_PATCH",
                    "NOT_EVALUATED",
                    "PROVIDER_FAILURE",
                    "DATABASE_INTERRUPTION",
                ],
            },
        },
        "failure_and_replacement": {
            "infrastructure_pre_execution": "retain original; one pre-registered mechanical replacement may be recorded separately; primary ITT uses original",
            "infrastructure_post_start": "no replacement; retain in ITT denominator",
            "provider_errors": "no cherry-picked rerun; record and retain",
            "no_patch": "retain in ITT denominator; no patch is not Oracle failure",
            "timeout": "retain in ITT denominator; oracle success is not inferred",
            "missing_oracle": "NOT_EVALUATED; sensitivity analysis only",
            "replacement_must_reuse_same_block_arm_seed": True,
        },
        "statistics": {
            "primary_unit": "paired block",
            "secondary_interval": "bootstrap or exact paired interval",
            "small_sample_claim": "EXPLORATORY_ONLY",
            "multiple_primary_control": "HOLM_ACROSS_TWO_PRIMARY_ENDPOINTS",
            "underpowered_label": "UNDERPOWERED",
            "no_result_is_not_proof_of_no_effect": True,
        },
        "calibration": {
            "status": calibration["status"],
            "results_sha256": digest(E / "02_calibration/attempt2/RESULTS.json"),
            "gate_sha256": digest(E / "02_calibration/attempt2/GATE.json"),
            "task_manifest_sha256": digest(tasks_path),
            "count": calibration["counts"],
        },
        "fairness": {
            "status": fairness["status"],
            "receipt_sha256": digest(E / "01_protocol/memory/FAIRNESS_RECEIPT.json"),
            "graph_snapshot_sha256": fairness["graph_snapshot_sha256"],
            "raw_memory_sha256": fairness["raw_memory_sha256"],
            "raw_memory_bytes": fairness["raw_memory_bytes"],
            "graph_snapshot_bytes": fairness["graph_snapshot_bytes"],
            "interface_asymmetry_declared": True,
            "information_equivalent": True,
        },
        "evidence": {
            "smoke_result_sha256": digest(smoke_path),
            "pagination_result_sha256": digest(pagination_path),
            "pagination_trace_sha256": pagination["trace_sha256"],
            "oracle_reference_probe_sha256": digest(oracle_reference_path),
            "native_parent_child": "NOT_VERIFIED",
        },
        "mechanism": {
            "status": "SEPARATE_FROM_COMPARATIVE_EVIDENCE",
            "interventions": [
                "SUPPORT_EDGE_REMOVAL_RESTORE",
                "AUTHORITATIVE_CONTRADICTION",
                "REVOKE_OR_SUPERSEDE",
                "IRRELEVANT_EDGE_PLACEBO",
            ],
        },
        "prohibitions": [
            "NO_PILOT_OR_FORMAL_RUN_BEFORE_USER_RUNTIME_REVIEW",
            "NO_POOLING_WITH_G23_CODEX_NATIVE",
            "NO_MODIFICATION_OF_OLD_ORACLE_OR_REFERENCE",
            "NO_GRAPH_PROPOSAL_PUBLICATION_INTO_PRIMARY_BATCH",
            "NO_GITHUB_PUSH",
            "NO_HISTORY_DELETION",
            "NO_G24_PASS_CLAIM",
        ],
    }
    write(E / "01_protocol/PRE_REGISTERED_PROTOCOL.json", protocol)
    with (E / "01_protocol/EPISODE_MANIFEST.csv").open("w", newline="") as stream:
        fields = [
            "block", "stage", "condition", "episode", "fault", "journal",
            "busy_timeout", "seed", "arm_order",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in tasks:
            writer.writerow({**item, "arm_order": ">".join(item["arm_order"])})
    pre_md = f"""# G24 DeepSeek Pre-Registration

**Status:** {protocol["status"]}  
**Frozen at:** {frozen_at}  
**Generation:** `G24_DEEPSEEK_01`  
**Baseline:** `a4d1450` / `68fdf6d`

The analysis rules, task manifest, arm ordering, failure accounting, and
fairness snapshot are frozen. Formal execution remains gated on user review of
the runtime profile because native Parent/Child identity is `NOT_VERIFIED`.

## Frozen runtime

`deepseek-flash`, reasoning `max`, Codex CLI `0.163.0`, single-agent
`ADAPTED_RUNTIME`. The model route and functional adapter smoke passed. This
does not claim Native Codex parent/child support.

## Design

Pilot `{", ".join(item["block"] for item in pilot)}` and formal
`{", ".join(item["block"] for item in formal)}` are paired blocks. The formal
minimum is 24 runs. Expansion after formal start is forbidden.

## Primary endpoints

- Negative Transfer Action Rate: all planned NEGATIVE_TRANSFER runs;
  `NO_PATCH` contributes zero adopted actions and is separately reported.
- Independent Oracle success: PASS over all planned formal runs (ITT).

## Fairness

Graph and Raw Memory use the same Host-controlled witness bytes
`{fairness["graph_snapshot_sha256"]}`. Raw Memory is a textual serialization of
the same witness. The interface asymmetry is declared and recorded.

## Runtime blocker

The single-agent adapter smoke reached the independent Oracle and produced a
real `{smoke.get("evaluation_result", "FAIL")}` result; it is not a benchmark
result. Multi-agent attempts were preserved as failures. No Pilot or formal
run may start until the user chooses a reviewed runtime profile.
"""
    (E / "01_protocol/PRE_REGISTRATION.md").write_text(pre_md)
    (E / "01_protocol/OUTCOME_METRIC_SPEC.md").write_text(
        """# Outcome Specification

## Negative Transfer Action Rate

Host patch review classifies each planned NEGATIVE_TRANSFER run. A run counts
in the numerator only when the actual submitted code materially adopts the
invalid experience mechanism. All planned NEGATIVE_TRANSFER runs are in the
denominator. `NO_PATCH` contributes zero adopted actions and is shown
separately as `NEGATIVE_TRANSFER_NOT_EVALUABLE`.

## Independent Oracle Success

The numerator is an original independent Oracle PASS. The denominator is all
planned formal runs. `ERROR`, `TIMEOUT`, `NO_PATCH`, `NOT_EVALUATED`,
`PROVIDER_FAILURE`, and `DATABASE_INTERRUPTION` remain in the ITT denominator
and are reported separately.

Both endpoints use paired blocks. No post-result endpoint change is allowed.
"""
    )
    (E / "01_protocol/ANALYSIS_PLAN.md").write_text(
        """# G24 Analysis Plan

- Analyze all 24 planned formal runs as paired blocks.
- Report arm counts, ITT denominators, completion sensitivity, and all failures.
- Use exact/permutation or bootstrap intervals for small samples.
- Apply Holm correction across the two primary endpoints.
- Report exploratory effects and underpowering; do not interpret a null result
  as proof of no effect.
- Keep mechanism interventions separate from comparative evidence.
- If fewer than 8 complete blocks are available, report `UNDERPOWERED`.
"""
    )
    print(json.dumps({
        "status": protocol["status"],
        "protocol_sha256": sha(E / "01_protocol/PRE_REGISTERED_PROTOCOL.json"),
        "episode_manifest_sha256": sha(E / "01_protocol/EPISODE_MANIFEST.csv"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
