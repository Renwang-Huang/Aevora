"""Assemble the D0-D3 handoff receipt from sealed local evidence."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess

from audit import E, sha, write


def h(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    smoke_path = E / "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json"
    smoke = json.loads(smoke_path.read_text())
    run_id = smoke["run_id"]
    run = E / "09_evidence/smoke_runs" / run_id
    report = json.loads((run / "evaluation_report.json").read_text())
    runtime = json.loads((run / "runtime_metadata.json").read_text())
    pagination = json.loads((E / "09_evidence/PAGINATION_RESULT.json").read_text())
    reference = json.loads((E / "09_evidence/ORACLE_REFERENCE_PROBE.json").read_text())
    calibration = json.loads((E / "02_calibration/attempt2/GATE.json").read_text())
    calibration_rows = json.loads((E / "02_calibration/attempt2/RESULTS.json").read_text())
    fairness = json.loads((E / "01_protocol/memory/FAIRNESS_RECEIPT.json").read_text())
    fairness_verify = json.loads((E / "01_protocol/memory/FAIRNESS_VERIFICATION.json").read_text())
    protocol = json.loads((E / "01_protocol/PRE_REGISTERED_PROTOCOL.json").read_text())
    commit = subprocess.check_output(
        ["git", "-C", str(E / "worktree"), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(E / "worktree"), "rev-parse", "HEAD^{tree}"],
        text=True,
    ).strip()
    mcp_tools = []
    mcp_events = run / "aevora_mcp_events.jsonl"
    for line in mcp_events.read_text().splitlines():
        event = json.loads(line)
        if event.get("category") != "JSONRPC" or event.get("direction") != "PARTICIPANT_TO_OFFICIAL_SDK":
            continue
        request = json.loads(event["raw_json"])
        if request.get("method") == "tools/call":
            mcp_tools.append(request["params"]["name"])
    tool_counts = {name: mcp_tools.count(name) for name in sorted(set(mcp_tools))}
    provider = smoke.get("provider", {})
    d2 = {
        "status": "PARTIAL",
        "functional_adapter": "PASS",
        "functional_smoke_run": run_id,
        "functional_smoke_scope": "NON_SCORED",
        "provider": provider,
        "runtime": {
            "codex_cli": runtime.get("codex_version"),
            "agent_mode": "single",
            "model_requests": len(
                runtime.get("model_broker", {}).get("request_records", [])
            ),
            "effective_model": runtime.get("model_broker", {}).get("effective_model"),
            "effective_effort": runtime.get("model_broker", {}).get("effective_effort"),
        },
        "mcp_four_tools": tool_counts,
        "mcp_tools_all_present": set(tool_counts) == {
            "resolve_experience", "build_evidence_bundle",
            "record_decision", "propose_experience",
        },
        "mcp_pagination": {
            "status": pagination["status"],
            "production_wire_budget_changed": pagination["production_wire_budget_changed"],
            "test_wire_budget": 12000,
            "resolve_pages": pagination["resolve_pages"],
            "bundle_pages": pagination["bundle_pages"],
            "trace_sha256": pagination["trace_sha256"],
        },
        "code_modification": {
            "runtime_result": smoke.get("runtime_result"),
            "patch_sha256": report.get("submission", {}).get("sha256")
            or report.get("agent", {}).get("submission_sha256"),
            "submission_integrity": report.get("submission_integrity_status"),
            "public_tests": "PASS_4/4",
        },
        "independent_oracle": {
            "execution": "PASS",
            "model_smoke_result": report.get("overall_status"),
            "test_results": report.get("test_results"),
            "reference_patch_probe": reference["status"],
            "reference_probe_tests": reference["test_results"],
        },
        "native_parent_child": {
            "status": "NOT_VERIFIED",
            "attempts_preserved": True,
            "attempt_runs": [
                "deb69a35-2b8b-47fc-b969-7725fa0baee6",
                "d118dfd0-1555-416c-9ef4-358af3451b44",
                "a8087a97-88aa-477c-b64d-2a94779cdcf7",
                "ddd25b49-b262-445d-8e61-35efe624222f",
                "18214297-12ad-4690-bafe-25289469bb90",
            ],
            "reason": "DeepSeek/Codex 0.163.0 produced wait-only or thread-limit failures; no verified child terminal identity",
        },
        "private_oracle_exposure": "NO_EVIDENCE_OF_EXPOSURE",
        "formal_execution": "BLOCKED_BY_RUNTIME_REVIEW",
    }
    d3 = {
        "status": "PASS",
        "calibration_gate": calibration,
        "calibration_rows": len(calibration_rows),
        "junit_files": len(list((E / "02_calibration/attempt2/junit").glob("*.xml"))),
        "calibration_results_sha256": sha(E / "02_calibration/attempt2/RESULTS.json"),
        "calibration_gate_sha256": sha(E / "02_calibration/attempt2/GATE.json"),
        "frozen_tasks_sha256": sha(E / "01_protocol/TASKS_FROZEN.json"),
        "arm_order_balance": json.loads((E / "01_protocol/ARM_ORDER_BALANCE.json").read_text()),
        "fairness": {
            **fairness,
            "verification": fairness_verify,
            "information_equivalent": fairness_verify["status"] == "PASS",
            "interface_asymmetry_declared": True,
        },
        "pre_registration": {
            "status": protocol["status"],
            "sha256": sha(E / "01_protocol/PRE_REGISTERED_PROTOCOL.json"),
            "frozen_at": protocol["frozen_at"],
            "runtime_profile": protocol["runtime"]["profile_id"],
            "runtime_review_required": True,
        },
        "targeted_tests": {
            "command": "pytest -q tests/test_g24_deepseek_adapter.py tests/test_codex_agent.py tests/test_gateway_broker.py tests/test_gateway_retry.py tests/test_completion_runtime.py tests/test_aevora_integration.py tests/test_participant.py tests/test_participant_sandbox.py",
            "result": "160 passed",
            "receipt": "commands/g24-adapter-tests/receipt.json",
        },
        "pilot": "NOT_RUN",
        "formal": "NOT_RUN",
    }
    receipt = {
        "schema": "aevora.g24.takeover.d0_d3/1.0",
        "run_id": E.name,
        "generated_at": protocol["frozen_at"],
        "takeover": "PARTIAL",
        "source_commit": commit,
        "source_tree": tree,
        "baseline_commit": "a4d1450139cfcaff3c0c278e2476b07b532aa44d",
        "baseline_tree": "68fdf6d3b045040d2b52d181e05cf84d7f36ce9e",
        "d0": "PASS",
        "d1": json.loads((E / "00_baseline/SETUP_RESULT.json").read_text())["status"],
        "d2": d2,
        "d3": d3,
        "pilot": "NOT_RUN",
        "formal": "NOT_RUN",
        "g24_r": "NOT_RUN",
        "formal_execution": "BLOCKED_BY_RUNTIME_REVIEW",
        "native_codex_claim": "NOT_MADE",
        "github_push": "NOT_PERFORMED",
        "history_deletion": "NOT_PERFORMED",
        "g24_pass_claim": "NOT_MADE",
    }
    write(E / "09_evidence/G24_D0_D3_RECEIPT.json", receipt)
    manifest = {
        "generation": E.name,
        "source_commit": commit,
        "source_tree": tree,
        "files": {
            name: {
                "sha256": sha(E / name),
                "bytes": (E / name).stat().st_size,
            }
            for name in (
                "IDENTITY.json",
                "01_protocol/TASKS_FROZEN.json",
                "01_protocol/ARM_ORDER_BALANCE.json",
                "01_protocol/PRE_REGISTERED_PROTOCOL.json",
                "01_protocol/PRE_REGISTRATION.md",
                "01_protocol/EPISODE_MANIFEST.csv",
                "01_protocol/OUTCOME_METRIC_SPEC.md",
                "01_protocol/ANALYSIS_PLAN.md",
                "01_protocol/ARM_EQUIVALENCE_MATRIX.csv",
                "02_calibration/attempt2/RESULTS.json",
                "02_calibration/attempt2/GATE.json",
                "09_evidence/ADAPTER_SMOKE_RESULT_SINGLE_ORACLE_FAIL.json",
                "09_evidence/PAGINATION_RESULT.json",
                "09_evidence/ORACLE_REFERENCE_PROBE.json",
                "09_evidence/G24_D0_D3_RECEIPT.json",
            )
        },
    }
    write(E / "09_evidence/G24_D0_D3_MANIFEST.json", manifest)
    with (E / "09_evidence/ADAPTER_SMOKE_ARTIFACTS.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["artifact", "sha256", "bytes"])
        for path in sorted(run.rglob("*")):
            if path.is_file():
                writer.writerow([
                    str(path.relative_to(E)),
                    sha(path),
                    path.stat().st_size,
                ])
    report_md = f"""# G24 D0-D3 Engineering Receipt

## Verdict

- D0 takeover freeze: **PASS**
- D1 isolated environment: **PASS**
- D2 adapter: **PARTIAL**
- D3 calibration/fairness/pre-registration: **PASS**
- Pilot: **NOT_RUN**
- Formal comparison: **NOT_RUN**
- G24-R: **NOT_RUN**

The single-agent DeepSeek functional smoke completed real model calls, code
modification, four MCP tool calls, pagination, and an independent Oracle run.
The Oracle rejected the model patch because it did not add the required
persistent stock-conservation constraint. The unchanged reference patch
subsequently passed the same Oracle 8/8. Native parent/child identity remains
**NOT_VERIFIED**; formal execution is therefore blocked pending runtime review.

## Source and calibration

- Source commit: `{commit}`
- Source tree: `{tree}`
- G2-3 baseline: `a4d1450` / `68fdf6d`
- Calibration: {calibration_rows.__len__()} runs; GATE `{calibration['status']}`
- Final calibration counts: `{json.dumps(calibration['counts'], sort_keys=True)}`
- Tasks frozen SHA256: `{sha(E / '01_protocol/TASKS_FROZEN.json')}`
- Pre-registration SHA256: `{sha(E / '01_protocol/PRE_REGISTERED_PROTOCOL.json')}`

## D2 smoke

- Model: `deepseek-flash`, effort `max`, Codex CLI `0.163.0`
- Effective model/effort: `{runtime.get('model_broker', {}).get('effective_model')}` / `{runtime.get('model_broker', {}).get('effective_effort')}`
- MCP tools observed: `{json.dumps(tool_counts, sort_keys=True)}`
- Pagination: resolve `{pagination['resolve_pages']}` page, bundle `{pagination['bundle_pages']}` pages
- Model run: participant runner `PASS`, submission integrity `{report.get('submission_integrity_status')}`, Oracle `{report.get('overall_status')}`
- Reference Oracle probe: `{reference['status']}` ({reference['test_results']['passed']}/{reference['test_results']['collected']})
- Native parent/child: `NOT_VERIFIED`

## Evidence

The machine-readable receipt is
`{E / '09_evidence/G24_D0_D3_RECEIPT.json'}`. Raw model events, MCP events,
gateway transport, patch, and Oracle artifacts are under
`{run}`. Full calibration JUnit files are under
`{E / '02_calibration/attempt2/junit'}`.
"""
    (E / "09_evidence/G24_D0_D3_RECEIPT.md").write_text(report_md)
    write(E / "CURRENT_STATUS.json", {
        "status": "D0_D3_COMPLETE_RUNTIME_REVIEW_REQUIRED",
        "d2": "PARTIAL",
        "d3": "PASS",
        "native_parent_child": "NOT_VERIFIED",
        "formal": "NOT_RUN",
        "next_action": "review single-agent adapted runtime or fix native child runtime before Pilot",
    })
    print(json.dumps({
        "status": "PASS",
        "d2": d2["status"],
        "d3": d3["status"],
        "calibration_rows": d3["calibration_rows"],
        "source_commit": commit,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
