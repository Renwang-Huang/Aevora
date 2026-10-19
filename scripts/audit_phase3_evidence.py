"""Supplement an existing real Phase3 archive without changing its task score.

Reparse official events, check strict evidence guards, and run the final full
developer suite. No model call, candidate execution, or reference substitution.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from uuid import UUID, uuid4

from validate_phase3 import ROOT, audit_native, contracts_pass, isolation_verdict
from tools.history_paths import history_path
from evaluator.runner import read_junit
from integrations.codex_trace import parse_trace


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def native_exit_matches_result(record, formal):
    expected = {"PASS": 0, "FAIL": 1, "ERROR": 2, "TIMEOUT": 3, "NOT_IMPLEMENTED": 4}
    return (formal.get("overall_status") in expected and not record.get("timed_out", True)
            and record.get("exit_code") == expected[formal["overall_status"]])


def oracle_evidence_valid(formal):
    audits = formal.get("database_oracle")
    if not isinstance(audits, list) or not audits:
        return False
    valid = all(isinstance(x, dict) and type(x.get("consistent")) is bool
                and isinstance(x.get("violations"), list)
                and x["consistent"] == (not x["violations"]) for x in audits)
    return valid and (formal.get("evaluation_result") != "PASS" or all(x["consistent"] for x in audits))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-id", required=True)
    args = parser.parse_args()
    validation_id = str(UUID(args.validation_id))
    archive = ROOT / "runs/validation-phase3" / validation_id
    original = load(archive / "validation.json")
    output = archive / ("audit-" + str(uuid4()))
    output.mkdir()
    started = now()
    checks = {}
    formal_record = next(c for c in original["commands"] if c["label"] == "native-episode-A")
    formal = load(ROOT / formal_record["stdout"])
    directory = ROOT / "runs" / formal["run_id"]
    runtime = load(directory / "runtime_metadata.json")
    checks.update(audit_native(directory, formal))
    checks["native_exit_matches_result_without_timeout"] = native_exit_matches_result(formal_record, formal)
    reparsed = parse_trace(directory / "codex_events.jsonl", output / "reparsed_trace.jsonl", formal["run_id"])
    (output / "reparsed_observations.json").write_text(json.dumps(reparsed, indent=2) + "\n")
    checks["official_stream_complete"] = reparsed["integrity"]["status"] == "COMPLETE" and reparsed["turn_status"] == "COMPLETED"
    checks["official_thread_and_children_match"] = (
        reparsed["thread_id"] == runtime["thread_id"]
        and reparsed["subagents"] == runtime["subagents"]
        and reparsed["subagents"]["verified_count"] >= 2)
    checks["integration_sources_unchanged"] = all(
        digest(ROOT / name) == expected for name, expected in runtime["integration_fingerprints"].items())

    isolation_record = next(c for c in original["commands"] if c["label"] == "native-command-isolation")
    probe = load(ROOT / isolation_record["stdout"])
    # Inspect the archived Python literal; never execute archived probe code.
    code = isolation_record["argv"][-1]
    assignment = next(n for n in ast.parse(code).body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "targets" for t in n.targets))
    targets = ast.literal_eval(assignment.value)
    names = {"hidden_tests", "reference_patch", "private_manifest", "maintainer_source",
             "other_run", "trusted_auth", "host_auth"}
    checks["all_fourteen_isolation_targets_present"] = set(targets) == names | {"proc_root_" + n for n in names}
    checks["actual_trusted_targets_exist"] = all(Path(value).exists() for key, value in targets.items()
        if key in names - {"host_auth"})
    checks["strict_isolation_guard"] = isolation_verdict(probe, targets, isolation_record["exit_code"]) == "PASS"
    checks["identity_not_mounted_and_state_removed"] = runtime["credentials_in_participant"] is False and formal["agent_state_cleanup"] == "PASS"

    regression = load(ROOT / original["phase2_regression_archive"] / "validation.json")
    old_id = re.search(r"Validation ID：`([^`]+)`", history_path(ROOT, "PHASE2_VALIDATION_REPORT.md").read_text()).group(1)
    previous = load(ROOT / "runs/validation-phase2" / old_id / "validation.json")
    old_tests = previous["developer_tests"]["tests"]
    current_tests = {t["nodeid"]: t["outcome"] for t in regression["developer_tests"]["tests"]}
    checks["original_107_identities_retained"] = len(old_tests) == 107 and all(current_tests.get(t["nodeid"]) == "PASS" for t in old_tests)
    original_fingerprints = previous["repeats"][0]["fingerprints"]
    checks["original_hidden_evaluator_private_manifest_and_suite_unchanged"] = all(
        original_fingerprints[key] == formal["fingerprints"][key]
        for key in ("evaluator", "private_manifest_sha256", "test_suite"))
    checks["regression_all_checks_and_commands_pass"] = regression["conclusion"] == "PASS" and all(c["passed"] for c in regression["checks"]) and all(c["matches_expectation"] for c in regression["commands"])
    repeats = regression["repeats"]
    checks["ten_independent_buggy_reference_pairs"] = (
        len(repeats) == 20 and len({r["run_id"] for r in repeats}) == 20
        and {(r["round"], r["kind"]) for r in repeats} == {(i, k) for i in range(1, 11) for k in ("buggy", "reference")}
        and all(r["status"] == ("FAIL" if r["kind"] == "buggy" else "PASS")
                and r["counts"]["collected"] == 14 and r["counts"]["skipped"] == 0 for r in repeats))
    checks["trusted_oracle_evidence_matches_task_result"] = oracle_evidence_valid(formal)

    command = [sys.executable, "-m", "pytest", "-q", "--junitxml", str(output / "developer.junit.xml")]
    test_start = now()
    with (output / "developer.stdout.log").open("wb") as stdout, (output / "developer.stderr.log").open("wb") as stderr:
        completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=180)
    results = read_junit(output / "developer.junit.xml")
    checks["final_full_developer_suite_pass"] = contracts_pass(results, completed.returncode)
    final_ids = {t["nodeid"]: t["outcome"] for t in results["tests"]}
    checks["original_107_pass_in_final_suite"] = all(final_ids.get(t["nodeid"]) == "PASS" for t in old_tests)
    summary = {
        "audit_id": output.name, "validation_id": validation_id, "run_id": formal["run_id"],
        "started_at": started, "ended_at": now(), "conclusion": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks, "task_result_unchanged": formal["evaluation_result"],
        "inputs": {str(p.relative_to(ROOT)): digest(p) for p in (
            archive / "validation.json", directory / "evaluation_report.json", directory / "runtime_metadata.json",
            directory / "submission.diff", directory / "codex_events.jsonl", directory / "agent_trace.jsonl")},
        "developer_tests": results, "command": {"argv": command, "command": shlex.join(command),
            "exit_code": completed.returncode, "started_at": test_start, "ended_at": now(),
            "stdout": str((output / "developer.stdout.log").relative_to(ROOT)),
            "stderr": str((output / "developer.stderr.log").relative_to(ROOT))},
        "script_sha256": digest(Path(__file__)),
        "validation_script_sha256": digest(ROOT / "scripts/validate_phase3.py"),
    }
    (output / "audit.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"archive": str(output.relative_to(ROOT)), "conclusion": summary["conclusion"],
                      "passed": results["passed"], "collected": results["collected"],
                      "failed_checks": [k for k, v in checks.items() if not v]}))
    return 0 if summary["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
