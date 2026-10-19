#!/usr/bin/env python3
"""Actual scripts/orderflow lifecycle regression; use host Python to launch it."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="New independent evidence directory")
    args = parser.parse_args()
    archive = args.archive.absolute()
    archive.mkdir(parents=True, exist_ok=False)
    records = []

    def execute(label, arguments, expected_exit, expected_status=None):
        output = archive / label
        output.mkdir()
        argv = [str(ROOT / "scripts/orderflow"), "--runs-root", str(archive / "runs"), *arguments]
        clock = time.monotonic()
        started = datetime.now(timezone.utc).isoformat()
        with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
            result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=180)
        try:
            report = json.loads((output / "stdout.log").read_text())
        except (ValueError, UnicodeError):
            report = {}
        tests = report.get("test_results") or {}
        status = report.get("overall_status", report.get("status", report.get("evaluation_status")))
        check = result.returncode == expected_exit and (expected_status is None or status == expected_status)
        if arguments[0] == "evaluate" and status in {"PASS", "FAIL"}:
            check = check and tests.get("errors") == 0 and tests.get("skipped") == 0
            check = check and report.get("submission_integrity_status") == "PASS" and report.get("environment_reset") is True
            if status == "PASS":
                check = check and tests.get("failed") == 0 and tests.get("passed") == tests.get("collected")
            else:
                check = check and tests.get("failed", 0) > 0
        receipt = {"label": label, "argv": argv, "cwd": str(ROOT), "started_at": started,
            "ended_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.monotonic() - clock,
            "exit_code": result.returncode, "expected_exit_code": expected_exit,
            "run_id": report.get("run_id"), "status": status, "checks_pass": check,
            "test_counts": {key: tests.get(key) for key in ("collected", "passed", "failed", "errors", "skipped")},
            "stdout_sha256": hashlib.sha256((output / "stdout.log").read_bytes()).hexdigest(),
            "stderr_sha256": hashlib.sha256((output / "stderr.log").read_bytes()).hexdigest()}
        (output / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        records.append(receipt)
        (archive / "summary.json").write_text(json.dumps({"result": "PASS" if all(r["checks_pass"] for r in records) else "FAIL", "commands": records}, indent=2) + "\n")
        print(json.dumps(receipt), flush=True)
        return report

    execute("validate-d", ["validate", "--episode", "D", "--variant", "v01"], 0, "IMPLEMENTED")
    prepared = execute("prepare-d", ["prepare", "--episode", "D", "--variant", "v01"], 0, "PREPARED")
    execute("report-prepared", ["report", "--run-id", prepared["run_id"]], 0, "PREPARED")
    execute("reset-d", ["reset", "--episode", "D"], 0, "RESET")
    cases = [("smoke-buggy", "SMOKE-001", None, "FAIL"),
        ("smoke-reference", "SMOKE-001", "SMOKE-001-current.diff", "PASS"),
        ("a-buggy", "A", None, "FAIL"), ("a-reference", "A", "A-v01.diff", "PASS"),
        ("d-buggy", "D", None, "FAIL"), ("d-reference", "D", "D-v01.diff", "PASS"),
        ("d-flock-alternative", "D", "D-v01-flock.diff", "PASS"),
        ("b-planned", "B", None, "NOT_IMPLEMENTED"), ("c-planned", "C", None, "NOT_IMPLEMENTED")]
    for label, episode, patch, expected in cases:
        arguments = ["evaluate", "--episode", episode]
        if patch:
            arguments += ["--submission", str(ROOT / "evaluator/reference_patches" / patch)]
        execute(label, arguments, {"PASS": 0, "FAIL": 1, "NOT_IMPLEMENTED": 4}[expected], expected)
    execute("invalid-submission", ["evaluate", "--episode", "D", "--submission", str(archive / "absent.diff")], 2, "ERROR")
    execute("evaluation-timeout", ["evaluate", "--episode", "D", "--timeout", "0.1"], 3, "TIMEOUT")
    return 0 if all(record["checks_pass"] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
