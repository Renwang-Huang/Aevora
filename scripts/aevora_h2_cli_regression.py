#!/usr/bin/env python3
"""Actual inherited CLI contracts in the explicitly selected H2 runtime.

Run inside the trusted launcher; no nested personal-runtime shell wrapper.
Actual inner exits and commands are preserved, including expected FAIL cases.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cli-module", default="benchmark.cli", choices=("benchmark.cli", "benchmark.h2_cli"))
    args = parser.parse_args(argv)
    archive = args.output.absolute()
    archive.mkdir(parents=True, exist_ok=False)
    records = []
    prefix = [sys.executable, "-m", args.cli_module, "--runs-root", str(archive / "runs")]

    def execute(label, arguments, expected_exit, expected_status, count=None):
        out = archive / label
        out.mkdir()
        command = prefix + arguments
        started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
        with (out / "stdout.log").open("xb") as stdout, (out / "stderr.log").open("xb") as stderr:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=180, check=False)
        try:
            report = json.loads((out / "stdout.log").read_text())
        except (ValueError, UnicodeError):
            report = {}
        status = report.get("overall_status", report.get("status", report.get("evaluation_status")))
        tests = report.get("test_results") or {}
        passed = result.returncode == expected_exit and status == expected_status
        if count is not None:
            passed = (passed and tests.get("collected") == count and tests.get("errors") == 0
                      and tests.get("skipped") == 0 and report.get("submission_integrity_status") == "PASS"
                      and report.get("environment_reset") is True)
            if expected_status == "PASS":
                passed = passed and tests.get("passed") == count and tests.get("failed") == 0
            else:
                passed = passed and tests.get("failed", 0) > 0
        receipt = {"label": label, "argv": command, "cwd": str(ROOT), "started_at": started,
                   "ended_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.monotonic()-clock,
                   "exit_code": result.returncode, "expected_exit_code": expected_exit,
                   "expected_status": expected_status, "run_id": report.get("run_id"), "status": status,
                   "checks_pass": bool(passed), "test_counts": {k: tests.get(k) for k in (
                       "collected", "passed", "failed", "errors", "skipped")},
                   "observed_runtime": report.get("runtime"),
                   "stdout_sha256": hashlib.sha256((out / "stdout.log").read_bytes()).hexdigest(),
                   "stderr_sha256": hashlib.sha256((out / "stderr.log").read_bytes()).hexdigest()}
        (out / "command.json").write_text(json.dumps(receipt, indent=2)+"\n")
        records.append(receipt)
        (archive / "summary.json").write_text(json.dumps({"status": "PASS" if all(x["checks_pass"] for x in records) else "FAIL",
            "scope": "Actual 15 inherited CLI checks; expected business FAIL is not a successful submission",
            "commands": records}, indent=2)+"\n")
        print(json.dumps(receipt), flush=True)
        return report

    execute("validate-d", ["validate", "--episode", "D", "--variant", "v01"], 0, "IMPLEMENTED")
    prepared = execute("prepare-d", ["prepare", "--episode", "D", "--variant", "v01"], 0, "PREPARED")
    if not prepared.get("run_id"):
        return 1
    execute("report-prepared", ["report", "--run-id", prepared["run_id"]], 0, "PREPARED")
    execute("reset-d", ["reset", "--episode", "D"], 0, "RESET")
    cases = [("smoke-buggy", "SMOKE-001", None, "FAIL", 8),
             ("smoke-reference", "SMOKE-001", "SMOKE-001-current.diff", "PASS", 8),
             ("a-buggy", "A", None, "FAIL", 14), ("a-reference", "A", "A-v01.diff", "PASS", 14),
             ("d-buggy", "D", None, "FAIL", 28), ("d-reference", "D", "D-v01.diff", "PASS", 28),
             ("d-flock-alternative", "D", "D-v01-flock.diff", "PASS", 28),
             ("b-planned", "B", None, "NOT_IMPLEMENTED", None), ("c-planned", "C", None, "NOT_IMPLEMENTED", None)]
    for label, episode, patch, verdict, count in cases:
        command = ["evaluate", "--episode", episode]
        if patch:
            command += ["--submission", str(ROOT / "evaluator/reference_patches" / patch)]
        execute(label, command, {"PASS":0, "FAIL":1, "NOT_IMPLEMENTED":4}[verdict], verdict, count)
    execute("invalid-submission", ["evaluate", "--episode", "D", "--submission", str(archive / "absent.diff")], 2, "ERROR")
    execute("evaluation-timeout", ["evaluate", "--episode", "D", "--timeout", "0.1"], 3, "TIMEOUT")
    return 0 if len(records) == 15 and all(row["checks_pass"] for row in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
