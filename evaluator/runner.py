"""Launch a trusted pytest oracle against a filesystem-isolated candidate."""

from datetime import datetime, timezone
from collections import Counter
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET


from evaluator.suites import get_suite


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_results() -> dict:
    return {"collected": 0, "passed": 0, "failed": 0, "errors": 0,
            "skipped": 0, "tests": []}


def read_junit(path: Path) -> dict:
    """Derive every outcome from a real testcase entry, not a PASS log string."""
    root = ET.parse(path).getroot()
    if root.tag not in {"testsuites", "testsuite"}:
        raise ValueError("Unexpected JUnit document root")
    for suite in root.iter("testsuite"):
        cases = list(suite.iter("testcase"))
        actual = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                  "errors": sum(c.find("error") is not None for c in cases),
                  "skipped": sum(c.find("skipped") is not None for c in cases)}
        for field, count in actual.items():
            if field in suite.attrib and int(suite.attrib[field]) != count:
                raise ValueError(f"JUnit declared {field} differs from testcase entries")
    summary = empty_results()
    for case in root.iter("testcase"):
        failures = list(case.findall("failure"))
        errors = list(case.findall("error"))
        skips = list(case.findall("skipped"))
        if sum(bool(items) for items in (failures, errors, skips)) > 1:
            raise ValueError("JUnit testcase has conflicting outcomes")
        duration = float(case.get("time", "0"))
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("JUnit testcase has invalid duration")
        if errors:
            outcome, key, details = "ERROR", "errors", errors
        elif failures:
            outcome, key, details = "FAIL", "failed", failures
        elif skips:
            outcome, key, details = "SKIPPED", "skipped", skips
        else:
            outcome, key, details = "PASS", "passed", []
        summary[key] += 1
        summary["collected"] += 1
        summary["tests"].append({
            "name": case.get("name", ""),
            "nodeid": f"{case.get('classname', '')}::{case.get('name', '')}",
            "outcome": outcome,
            "duration_seconds": duration,
            "message": "\n".join(
                item.get("message", "") + "\n" + (item.text or "") for item in details
            ).strip() or None,
        })
    return summary


def evaluate(workspace: Path, artifacts: Path, timeout_seconds: float = 20,
             expected_test_count: int | None = None, *, suite_id: str = "smoke",
             expected_tests: list[str] | tuple[str, ...] | None = None) -> dict:
    """Evaluate a registered suite through a fresh independent host pytest process.

    The supplied workspace is never put on the host's import path. Candidate
    Python runs only inside the sandbox started by the trusted RPC fixtures.
    The caller chooses an artifact directory under its trusted run store.
    """
    result = {
        "status": "ERROR", "pytest_exit_code": None,
        "test_results": empty_results(), "started_at": timestamp(),
        "ended_at": None, "errors": [], "artifacts": {},
    }
    try:
        suite = get_suite(suite_id)
        required = tuple(expected_tests) if expected_tests is not None else suite.expected_tests
        if not required or len(set(required)) != len(required) or required != suite.expected_tests:
            raise ValueError("Expected test identities differ from registered suite")
        expected_test_count = len(required) if expected_test_count is None else expected_test_count
        workspace, artifacts = Path(workspace).resolve(), Path(artifacts).resolve()
        if not workspace.is_dir() or not (workspace / "app").is_dir():
            raise ValueError("Submission must contain an app directory")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Evaluation timeout must be finite and positive")
        if type(expected_test_count) is not int or expected_test_count <= 0:
            raise ValueError("Expected test count must be a positive integer")
        artifacts.mkdir(parents=True, exist_ok=True)
        junit_path = artifacts / "junit.xml"
        stdout_path, stderr_path = artifacts / "pytest.stdout.log", artifacts / "pytest.stderr.log"
        # Reusing an artifact directory must retain an owned cleanup receipt
        # until the prior scope has actually been reaped. Never erase the only
        # recovery pointer before starting the next independent invocation.
        from evaluator.resource_recovery import recover_worker_scopes
        previous_resources = recover_worker_scopes(artifacts)
        result["previous_resource_cleanup"] = previous_resources
        if any(not row["cleanup_complete"] for row in previous_resources):
            raise ValueError("Prior owned worker resources could not be cleaned; refusing artifact reuse")
        # A failed second invocation must never consume a first invocation's XML.
        junit_path.unlink(missing_ok=True)
        # Independent API callers can reuse artifacts; old evidence is not a
        # current observation even when this invocation times out before tests.
        for pattern in ("concurrency-*.json", "oracle-*.json", "worker-*.stderr.log", "topology-*.json", "recovery-*.json", "pool-resource-*.json"):
            for old_artifact in artifacts.glob(pattern):
                old_artifact.unlink()
        command = [
            sys.executable, "-I", "-B", "-m", "pytest", str(suite.path),
            "-c", os.devnull, "-o", "addopts=", "--import-mode=importlib",
            "-p", "no:cacheprovider", "--junitxml", str(junit_path),
            "--basetemp", str(artifacts / "pytest-tmp"), "-q",
        ]
        environment = os.environ.copy()
        for variable in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
            environment.pop(variable, None)
        environment.update({
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "ORDERFLOW_EVALUATION_WORKSPACE": str(workspace),
            "ORDERFLOW_EVALUATION_ARTIFACTS": str(artifacts),
            "ORDERFLOW_EVALUATION_SUITE": suite.id,
            "ORDERFLOW_EXECUTION_STRATEGY": suite.execution_strategy,
        })
        timed_out = False
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command, cwd=artifacts, env=environment,
                stdout=stdout, stderr=stderr, start_new_session=True,
            )
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                # All workers inherit this group. Kill it even if pytest just
                # exited, because a worker may still be running at the deadline.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
        resource_recovery = recover_worker_scopes(artifacts)
        if resource_recovery:
            (artifacts / "recovery-owned-pool-resources.json").write_text(json.dumps(resource_recovery, indent=2) + "\n")
        if any(not row["cleanup_complete"] for row in resource_recovery):
            result["errors"].append("Owned worker resource cleanup could not be verified")
        result["pytest_exit_code"] = process.returncode
        result["artifacts"] = {
            "junit_xml": str(junit_path) if junit_path.exists() else None,
            "pytest_stdout": str(stdout_path), "pytest_stderr": str(stderr_path),
            "worker_logs": sorted(str(path) for path in artifacts.glob("worker-*.stderr.log")),
            "concurrency_records": sorted(str(path) for path in artifacts.glob("concurrency-*.json")),
            "oracle_records": sorted(str(path) for path in artifacts.glob("oracle-*.json")),
            "topology_records": sorted(str(path) for path in artifacts.glob("topology-*.json")),
            "recovery_records": sorted(str(path) for path in artifacts.glob("recovery-*.json")),
        }
        # These records are host observations persisted by trusted tests, not candidate assertions.
        result["concurrency_evidence"] = [json.loads(Path(p).read_text()) for p in result["artifacts"]["concurrency_records"]]
        result["database_oracle"] = [json.loads(Path(p).read_text()) for p in result["artifacts"]["oracle_records"]]
        result["worker_topology_evidence"] = [json.loads(Path(p).read_text()) for p in result["artifacts"]["topology_records"]]
        result["recovery_evidence"] = [json.loads(Path(p).read_text()) for p in result["artifacts"]["recovery_records"]]
        from evaluator.recovery_coverage import recovery_coverage, missing_required_recovery
        result["recovery_coverage"] = recovery_coverage(result["recovery_evidence"], required_points=(
            "before_commit", "transaction_committed", "before_response")
            if suite.execution_strategy == "shared-db-workers" else ())
        if junit_path.is_file():
            try:
                result["test_results"] = read_junit(junit_path)
            except (ET.ParseError, ValueError, OSError) as error:
                result["errors"].append(f"Invalid JUnit report: {error}")
        else:
            result["errors"].append("Pytest produced no JUnit report")
        tests = result["test_results"]
        if timed_out:
            result["status"] = "TIMEOUT"
            result["errors"].append(f"Evaluation exceeded {timeout_seconds:g} seconds")
        elif result["errors"]:
            result["status"] = "ERROR"
        elif tests["collected"] != expected_test_count:
            result["status"] = "ERROR"
            result["errors"].append(
                f"Expected {expected_test_count} tests, collected {tests['collected']}"
            )
        elif Counter(t["name"] for t in tests["tests"]) != Counter(required):
            result["status"] = "ERROR"
            result["errors"].append("JUnit test identities do not match the complete required test set")
        elif tests["skipped"]:
            result["status"] = "ERROR"
            result["errors"].append("Required hidden tests were skipped")
        elif tests["errors"]:
            result["status"] = "ERROR"
            result["errors"].extend(
                test["message"] or test["nodeid"] for test in tests["tests"]
                if test["outcome"] == "ERROR"
            )
        elif process.returncode == 1 and tests["failed"]:
            result["status"] = "FAIL"
        elif process.returncode == 0 and tests["failed"] == 0:
            missing_windows = missing_required_recovery(result["recovery_coverage"])
            if missing_windows:
                result["status"] = "ERROR"
                result["errors"].append("RECOVERY_EVIDENCE_UNVERIFIED: cannot verify required crash windows "
                                        + ", ".join(missing_windows) + "; this is not a business failure")
            else:
                result["status"] = "PASS"
        else:
            result["status"] = "ERROR"
            result["errors"].append(
                f"Pytest exit code {process.returncode} conflicts with test outcomes"
            )
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        result["ended_at"] = timestamp()
    return result
