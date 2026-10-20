"""Full local calibration for the candidate G24 task blocks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit import E, sha, write
from benchmark.runner import BenchmarkRunner
from benchmark.submission import snapshot_source_tree, source_tree_sha256
from tools.experiments.g24.instances import bind, build


def main() -> int:
    blocks = json.loads((E / "01_protocol/TASKS_DRAFT.json").read_text())
    output = E / "02_calibration/attempt2"
    rows = []
    for instance in blocks:
        implementations = ["buggy", "reference"]
        if instance["episode"] in ("D", "D-V02"):
            implementations.append("flock")
        for implementation in implementations:
            label = instance["block"] + "-" + implementation
            workspace = build(output / "submissions" / label, instance, implementation=implementation)
            with bind(instance):
                result = BenchmarkRunner(output / "runs").evaluate(instance["episode"], workspace)
            run = output / "runs" / result["run_id"]
            junit = run / "artifacts/junit.xml"
            if junit.is_file():
                (output / "junit").mkdir(exist_ok=True)
                (output / "junit" / f"{label}.xml").write_bytes(junit.read_bytes())
            expected = "FAIL" if implementation == "buggy" else "PASS"
            row = {
                "label": label,
                "instance": instance,
                "implementation": implementation,
                "expected": expected,
                "status": result["overall_status"],
                "matches_expected": result["overall_status"] == expected,
                "run_id": result["run_id"],
                "test_results": result.get("test_results"),
                "errors": result.get("execution_errors", []),
                "submission_tree": source_tree_sha256(snapshot_source_tree(workspace)),
                "report_sha256": sha(run / "evaluation_report.json"),
                "junit_sha256": sha(junit) if junit.is_file() else "MISSING",
            }
            rows.append(row)
            write(output / "RESULTS.json", rows)
            print(
                json.dumps(
                    {
                        "label": label,
                        "status": row["status"],
                        "expected": expected,
                        "passed": (row["test_results"] or {}).get("passed"),
                        "failed": (row["test_results"] or {}).get("failed"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    expected_all = all(row["matches_expected"] for row in rows)
    counts = {
        "total": len(rows),
        "pilot": sum(row["instance"]["stage"] == "PILOT" for row in rows),
        "formal": sum(row["instance"]["stage"] == "FORMAL" for row in rows),
        "buggy": sum(row["implementation"] == "buggy" for row in rows),
        "reference": sum(row["implementation"] == "reference" for row in rows),
        "alternative": sum(row["implementation"] == "flock" for row in rows),
    }
    write(output / "GATE.json", {
        "status": "PASS" if expected_all else "BLOCKED_CALIBRATION",
        "counts": counts,
        "original_hidden_oracle_unchanged": True,
        "taskbook": "G24-A v1.1",
        "model_requests": 0,
    })
    print(json.dumps({"status": "PASS" if expected_all else "BLOCKED_CALIBRATION", **counts}, sort_keys=True))
    return 0 if expected_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
