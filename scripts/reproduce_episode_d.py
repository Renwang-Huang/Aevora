"""Independent initializations through the real CLI, with command receipts."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.episodes.episode_d import build_episode_d_fixture


def run_record(directory, argv, *, timeout=150):
    directory.mkdir(parents=True, exist_ok=False)
    start, elapsed = datetime.now(timezone.utc).isoformat(), time.monotonic()
    timed_out = False
    with (directory / "stdout.log").open("wb") as out, (directory / "stderr.log").open("wb") as err:
        process = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)
    try:
        report = json.loads((directory / "stdout.log").read_text())
    except (ValueError, UnicodeError):
        report = {}
    record = {"argv": argv, "started_at": start, "ended_at": datetime.now(timezone.utc).isoformat(),
              "elapsed_seconds": time.monotonic() - elapsed, "exit_code": process.returncode,
              "collector_timeout": timed_out, "run_id": report.get("run_id"),
              "status": report.get("overall_status"), "test_results": report.get("test_results"),
              "submission_integrity": report.get("submission_integrity"),
              "fingerprints": report.get("fingerprints"), "execution_errors": report.get("execution_errors"),
              "stdout_sha256": hashlib.sha256((directory / "stdout.log").read_bytes()).hexdigest(),
              "stderr_sha256": hashlib.sha256((directory / "stderr.log").read_bytes()).hexdigest()}
    (directory / "command.json").write_text(json.dumps(record, indent=2) + "\n")
    return record, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="new, nonexistent output directory")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--strategy", choices=["all", "buggy", "reference", "flock", "split-ledger"], default="all")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 20:
        parser.error("rounds must be between 1 and 20")
    archive = args.archive.resolve()
    archive.mkdir(parents=True, exist_ok=False)
    chosen = ["buggy", "reference", "flock"] if args.strategy == "all" else [args.strategy]
    records, checks = [], []
    for strategy in chosen:
        patch = {"reference": ROOT / "evaluator/reference_patches/D-v01.diff",
                 "flock": ROOT / "evaluator/reference_patches/D-v01-flock.diff",
                 "split-ledger": ROOT / "evaluator/reference_patches/D-v01-split-ledger.diff"}.get(strategy)
        for index in range(1, args.rounds + 1):
            argv = [sys.executable, "-m", "benchmark.cli", "--runs-root", str(archive / "runs"),
                    "evaluate", "--episode", "D", "--variant", "v01"]
            if patch is not None:
                argv += ["--submission", str(patch)]
            record, report = run_record(archive / f"{strategy}-{index:02d}", argv)
            record.update(strategy=strategy, round=index)
            expected = "FAIL" if strategy in {"buggy", "split-ledger"} else "PASS"
            tests = report.get("test_results") or {}
            valid = record["status"] == expected and record["exit_code"] == (1 if expected == "FAIL" else 0)
            valid = valid and tests.get("errors") == 0 and tests.get("skipped") == 0
            valid = valid and report.get("submission_integrity_status") == "PASS" and report.get("environment_reset") is True
            if expected == "FAIL":
                valid = valid and any(not oracle.get("consistent", False) for oracle in report.get("database_oracle", []))
            checks.append({"strategy": strategy, "round": index, "run_id": record["run_id"], "expected": expected,
                           "actual": record["status"], "exit_code": record["exit_code"], "checks_pass": valid,
                           "test_counts": {k: tests.get(k) for k in ("collected", "passed", "failed", "errors", "skipped")},
                           "failure_reasons": [{"name": t["name"], "message": t["message"]} for t in tests.get("tests", []) if t["outcome"] != "PASS"]})
            records.append(record)
            (archive / "summary.json").write_text(json.dumps({"checks": checks, "commands": records,
                       "result": "PASS" if all(c["checks_pass"] for c in checks) else "FAIL"}, indent=2) + "\n")
            print(json.dumps({k:v for k,v in checks[-1].items() if k != "failure_reasons"}), flush=True)
    return 0 if all(c["checks_pass"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
