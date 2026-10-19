"""Focused calibration for a single versioned block."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from audit import E, sha, write
from benchmark.runner import BenchmarkRunner
from tools.experiments.g24.instances import bind, build


def main() -> int:
    block_id = sys.argv[1]
    implementation = sys.argv[2]
    instance = next(
        item for item in json.loads((E / "01_protocol/TASKS_DRAFT.json").read_text())
        if item["block"] == block_id
    )
    output = E / "02_calibration" / f"{block_id}-{implementation}-probe"
    workspace = build(output / "submission", instance, implementation=implementation)
    with bind(instance):
        result = BenchmarkRunner(output / "runs").evaluate(instance["episode"], workspace)
    run = output / "runs" / result["run_id"]
    summary = {
        "block": block_id,
        "implementation": implementation,
        "status": result["overall_status"],
        "run_id": result["run_id"],
        "test_results": result.get("test_results"),
        "errors": result.get("execution_errors", []),
        "report_sha256": sha(run / "evaluation_report.json"),
    }
    write(output / "PROBE_RESULT.json", summary)
    print(json.dumps({
        "block": block_id,
        "implementation": implementation,
        "status": summary["status"],
        "passed": summary["test_results"]["passed"],
        "failed": summary["test_results"]["failed"],
    }, sort_keys=True))
    return 0 if result["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
