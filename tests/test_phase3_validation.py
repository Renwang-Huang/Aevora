"""Acceptance evidence guards, not synthetic native-agent success evidence."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("phase3_validation", Path(__file__).resolve().parents[1] / "scripts/validate_phase3.py")
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


@pytest.mark.parametrize("probe,exit_code,expected", [
    ({"public_source": True, "denied": {}}, 0, "PARTIAL"),
    ({"public_source": True, "denied": {"private": True}}, 0, "PASS"),
    ({"public_source": True, "denied": {"private": False}}, 0, "FAIL"),
    ({"public_source": True, "denied": {"private": True}}, 1, "PARTIAL"),
    ({"public_source": True, "denied": {"private": 1}}, 0, "PARTIAL"),
    ("", 0, "PARTIAL"),
])
def test_isolation_guard_requires_all_real_targets(probe, exit_code, expected):
    assert validation.isolation_verdict(probe, {"private": "/trusted/private"}, exit_code) == expected


@pytest.mark.parametrize("count,passed,skipped,exit_code,expected", [
    (0, 0, 0, 0, False),
    (3, 3, 0, 0, True),
    (3, 2, 1, 0, False),
    (3, 3, 0, 1, False),
])
def test_contract_guard_rejects_empty_or_skipped_suites(count, passed, skipped, exit_code, expected):
    results = {"collected": count, "passed": passed, "failed": 0, "errors": 0, "skipped": skipped}
    assert validation.contracts_pass(results, exit_code) is expected


def load_audit():
    # Its sibling import is a normal script import, not participant code.
    import sys
    monkey_path = str(Path(__file__).resolve().parents[1] / "scripts")
    sys.path.insert(0, monkey_path)
    try:
        spec = importlib.util.spec_from_file_location("phase3_evidence_audit", Path(monkey_path) / "audit_phase3_evidence.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(monkey_path)


def test_evidence_audit_accepts_real_task_failure_exit():
    audit = load_audit()
    assert audit.native_exit_matches_result({"exit_code": 1, "timed_out": False}, {"overall_status": "FAIL"})
    assert not audit.native_exit_matches_result({"exit_code": 0, "timed_out": False}, {"overall_status": "FAIL"})
    assert not audit.native_exit_matches_result({"exit_code": 0, "timed_out": True}, {"overall_status": "PASS"})


def test_evidence_audit_preserves_oracle_failure_without_task_pass():
    audit = load_audit()
    inconsistent = [{"consistent": False, "violations": ["inventory and ledger differ"]}]
    assert audit.oracle_evidence_valid({"evaluation_result": "FAIL", "database_oracle": inconsistent})
    assert not audit.oracle_evidence_valid({"evaluation_result": "PASS", "database_oracle": inconsistent})
    assert not audit.oracle_evidence_valid({"evaluation_result": "FAIL", "database_oracle": []})
    assert not audit.oracle_evidence_valid({"evaluation_result": "FAIL", "database_oracle": [{"consistent": True, "violations": ["contradiction"]}]})
