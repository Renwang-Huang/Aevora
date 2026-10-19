"""Bounded serial real Runner validation; preserves every attempt and reset."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.h2_cli import register_h2
from benchmark.runner import BenchmarkRunner
from scripts.aevora_h2_audit import sources, now, write


def execution_sources():
    # Freeze the complete execution boundary. New reports and G3 collectors may
    # be developed concurrently; they cannot alter this candidate/harness/core.
    rows = sources()
    return {name: record for name, record in rows.items() if name.startswith(
        ("app/", "benchmark/", "evaluator/", "integrations/", "aevora_core/src/", "tests/"))
        or name == "scripts/aevora_h2_dv02_validation.py"}


def run(destination, repetitions, strategies):
    register_h2()
    destination.mkdir(parents=True, exist_ok=False)
    before = execution_sources()
    write(destination / "SOURCE_EPOCH.json", {"files": before, "recorded_at": now()})
    runner = BenchmarkRunner(destination / "runs")
    rows = []
    expected = {"buggy": "FAIL", "reference": "PASS", "flock": "PASS", "local_lock": "FAIL", "blind_cleanup": "FAIL"}
    for index in range(1, repetitions + 1):
        for strategy in strategies:
            patch = None if strategy == "buggy" else ROOT / f"evaluator/reference_patches/D-V02-{strategy}.diff"
            report = runner.evaluate("D-V02", patch, variant="v02")
            tests = report.get("test_results") or {}
            directory = runner.runs_root / report["run_id"]
            matrix_path = report.get("artifacts", {}).get("request_recovery_matrix")
            matrix = json.loads(Path(matrix_path).read_text()) if matrix_path else {"status": "UNVERIFIED"}
            row = {"round": index, "strategy": strategy, "run_id": report["run_id"],
                "expected": expected[strategy], "actual": report["overall_status"],
                "expected_classification_observed": report["overall_status"] == expected[strategy],
                "pytest_exit_code": report.get("pytest_exit_code"),
                "test_counts": {key: tests.get(key) for key in ("collected", "passed", "failed", "errors", "skipped")},
                "failures": [{"name": test["name"], "outcome": test["outcome"], "message": test["message"]}
                             for test in tests.get("tests", []) if test["outcome"] != "PASS"],
                "execution_errors": report["execution_errors"], "request_recovery": matrix["status"],
                "report": str(directory / "evaluation_report.json"),
                "report_sha256": sha256((directory / "evaluation_report.json").read_bytes()).hexdigest(),
                "submission_sha256": (report.get("submission") or {}).get("sha256"),
                "evaluator_fingerprint": (report.get("fingerprints") or {}).get("evaluator", {}).get("sha256")}
            rows.append(row)
            with (destination / "ATTEMPTS.jsonl").open("a") as output:
                output.write(json.dumps(row, sort_keys=True) + "\n")
            print(json.dumps({key: row[key] for key in ("round", "strategy", "run_id", "actual", "test_counts", "request_recovery")}), flush=True)
    after = execution_sources()
    source_unchanged = before == after
    write(destination / "SOURCE_AFTER.json", {"files": after, "recorded_at": now(), "unchanged": source_unchanged})
    resets = [runner.reset("D-V02")]
    summary = {"status": "PASS" if source_unchanged and all(row["expected_classification_observed"]
               and row["request_recovery"] == "COMPLETE" for row in rows) else "FAIL",
        "repetitions": repetitions, "strategies": strategies, "attempt_count": len(rows),
        "rows": rows, "source_unchanged": source_unchanged, "resets": resets,
        "scope": "Real independent pytest executions; no missing/failed attempt excluded",
        "source_scope": "All app, benchmark, evaluator, integrations, core, developer/public tests and this collector; reports/G3-only collectors excluded"}
    write(destination / "SUMMARY.json", summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--strategy", action="append", choices=("buggy", "reference", "flock", "local_lock", "blind_cleanup"))
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 10:
        parser.error("repetitions must be 1..10")
    raise SystemExit(run(args.destination.absolute(), args.repetitions,
                        args.strategy or ["buggy", "reference", "flock", "local_lock"]))
