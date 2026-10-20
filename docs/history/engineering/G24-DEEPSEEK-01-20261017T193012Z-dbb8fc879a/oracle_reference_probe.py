"""Trusted reference-patch Oracle probe; not a model run."""
from __future__ import annotations

import json
from pathlib import Path

from audit import E, sha, write
from benchmark.manifest import load_manifest
from benchmark.registry import get_episode
from benchmark.runner import BenchmarkRunner
from benchmark.submission import apply_verified_patch


def main() -> int:
    output = E / "09_evidence/oracle_reference_probe"
    workspace = get_episode("SMOKE-001").build(output / "workspace", None)
    patch = E / "worktree/evaluator/reference_patches/SMOKE-001-current.diff"
    receipt = apply_verified_patch(workspace, patch)
    result = BenchmarkRunner(output / "runs").evaluate("SMOKE-001", workspace)
    run = output / "runs" / result["run_id"]
    summary = {
        "scope": "TRUSTED_REFERENCE_PATCH_ORACLE_PROBE_NOT_MODEL",
        "status": result["overall_status"],
        "run_id": result["run_id"],
        "patch_sha256": sha(patch),
        "patch_integrity": receipt,
        "test_results": result.get("test_results"),
        "errors": result.get("execution_errors", []),
        "report_sha256": sha(run / "evaluation_report.json"),
        "taskbook_sha256": sha(E / "01_protocol/PRE_REGISTERED_PROTOCOL.json"),
    }
    write(E / "09_evidence/ORACLE_REFERENCE_PROBE.json", summary)
    print(json.dumps({
        "status": summary["status"],
        "passed": summary["test_results"]["passed"],
        "failed": summary["test_results"]["failed"],
    }, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
