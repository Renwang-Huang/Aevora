"""Evaluate the actual failed-adapter Smoke patch with the independent Oracle.

This is a post-run diagnostic only. It never substitutes a reference patch and
does not change the original Adapter ERROR or its failure classification.
"""
from __future__ import annotations

import json
from pathlib import Path

from audit import E, now, sha, write
from benchmark.runner import BenchmarkRunner


SOURCE_RUN = E / "09_evidence/smoke_runs/890b8b07-7cbd-4a75-ad66-cfe9b47fec4b"
DIAGNOSTIC_ROOT = E / "09_evidence/native_oracle_diagnostic"


def main() -> int:
    patch = SOURCE_RUN / "submission.diff"
    if not patch.is_file():
        raise SystemExit("NATIVE_PATCH_MISSING")
    runner = BenchmarkRunner(DIAGNOSTIC_ROOT / "runs")
    prepared = runner.prepare("SMOKE-001")
    if prepared.get("overall_status") != "PREPARED":
        raise SystemExit("ORACLE_DIAGNOSTIC_PREPARE_FAILED")
    report = runner.evaluate(
        "SMOKE-001",
        submission=patch,
        run_id=prepared["run_id"],
    )
    result = {
        "schema": "aevora.g24.native.oracle_diagnostic/1.0",
        "status": "PASS" if report.get("overall_status") == "PASS" else "FAIL",
        "classification": "POST_RUN_INDEPENDENT_ORACLE_DIAGNOSTIC_NOT_ADAPTER_RESULT",
        "source_adapter_run": SOURCE_RUN.name,
        "source_adapter_status": "ERROR",
        "source_adapter_failure_kind": "DELEGATION_BOUNDARY_VIOLATION",
        "patch_sha256": sha(patch),
        "oracle_run_id": report.get("run_id"),
        "oracle_report": str(
            DIAGNOSTIC_ROOT / "runs" / report["run_id"] / "evaluation_report.json"
        ),
        "oracle_overall_status": report.get("overall_status"),
        "oracle_evaluation_status": report.get("evaluation_status"),
        "oracle_tests": report.get("test_results"),
        "oracle_errors": report.get("execution_errors", []),
        "created": now(),
        "note": "The actual Agent patch is evaluated unchanged; no reference patch is used.",
    }
    write(DIAGNOSTIC_ROOT / "NATIVE_ORACLE_DIAGNOSTIC.json", result)
    print(json.dumps({
        "status": result["status"],
        "oracle_run_id": result["oracle_run_id"],
        "oracle_overall_status": result["oracle_overall_status"],
        "patch_sha256": result["patch_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
