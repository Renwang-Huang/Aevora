"""Six fresh D-v01 calibration sessions, with no collector total deadline.

This is a serial experiment collector, not an agent scheduler. Official Codex
owns native delegation. Trusted admission receipts must exist before execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def verify_freeze(gate):
    for relative, expected in gate["frozen_source_sha256"].items():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file() or ROOT not in path.resolve().parents:
            raise ValueError(f"Unsafe frozen source: {relative}")
        if digest(path) != expected:
            raise ValueError(f"Frozen source changed: {relative}")


def tls_probe(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Admission requires an HTTPS Gateway without URL credentials")
    start = time.monotonic()
    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=30) as raw:
        with ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname) as connection:
            return {"status": "PASS", "hostname": parsed.hostname,
                "tls_version": connection.version(), "certificate_sha256": hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest(),
                "elapsed_seconds": time.monotonic() - start, "checked_at": now(),
                "scope": "Verified socket/TLS only; no model request or identity file read"}


def host_observation():
    return {"observed_at": now(), "load_average": list(os.getloadavg()),
        "cpu_count": os.cpu_count(), "collector_pid": os.getpid(),
        "other_maintainer_heavy_work": "NONE_SCHEDULED",
        "qualification": "Host load is measured; absence of all unrelated host work cannot be attested"}


def collect_trial(directory, command, runs_root, *, snapshot_interval=10):
    """Wait for actual exit; cancellation is explicit and never a wall timeout."""
    from integrations.runtime_control import status_run
    directory.mkdir(parents=True, exist_ok=False)
    start, clock = now(), time.monotonic()
    before = {p.name for p in runs_root.iterdir()} if runs_root.exists() else set()
    interrupted = {"signal": None, "at": None}
    process = None
    saved_handlers = {}

    def stop(signum, frame):
        if interrupted["signal"] is None:
            interrupted.update(signal=signum, at=now())
            if process is not None and process.poll() is None:
                # Adapter receives TERM and cleans its own namespaces/cgroup.
                process.send_signal(signal.SIGTERM)

    for signum in (signal.SIGINT, signal.SIGTERM):
        saved_handlers[signum] = signal.signal(signum, stop)
    identified = None
    snapshots = directory / "snapshots.jsonl"
    next_snapshot = 0.0
    try:
        with (directory / "stdout.log").open("xb") as output, (directory / "stderr.log").open("xb") as errors:
            process = subprocess.Popen(command, stdout=output, stderr=errors, start_new_session=True)
            atomic_json(directory / "command.started.json", {"argv": command, "started_at": start,
                "collector_policy": "completion-aware", "collector_total_deadline_seconds": None,
                "process_pid": process.pid})
            while process.poll() is None:
                if runs_root.exists():
                    new = [p for p in runs_root.iterdir() if p.name not in before and p.is_dir() and not p.is_symlink()]
                    if len(new) == 1:
                        identified = new[0]
                    elif len(new) > 1:
                        raise RuntimeError("Concurrent Run creation violates the serial calibration protocol")
                current = time.monotonic()
                if identified is not None and current >= next_snapshot:
                    try:
                        observation = status_run(identified)
                    except (OSError, ValueError, RuntimeError) as error:
                        observation = {"run_id": identified.name, "status": "PARTIAL_SNAPSHOT",
                            "observed_at": now(), "availability": "UNAVAILABLE", "reason": str(error)}
                    observation["collector_elapsed_seconds"] = current - clock
                    with snapshots.open("a") as stream:
                        stream.write(json.dumps(observation, sort_keys=True) + "\n")
                    next_snapshot = current + snapshot_interval
                time.sleep(0.25)
            exit_code = process.wait()
    except BaseException:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            # No total run deadline: wait for explicit-stop cleanup to finish.
            process.wait()
        raise
    finally:
        for signum, handler in saved_handlers.items():
            signal.signal(signum, handler)
    report = {}
    # A quick failure/cancellation can create and finalize its Run between two
    # polls. Discover after exit as well, preserving its original terminal report.
    if identified is None and runs_root.exists():
        completed = [p for p in runs_root.iterdir() if p.name not in before and p.is_dir() and not p.is_symlink()]
        if len(completed) == 1:
            identified = completed[0]
    if identified is not None and (identified / "evaluation_report.json").is_file():
        report = json.loads((identified / "evaluation_report.json").read_text())
    else:
        try:
            report = json.loads((directory / "stdout.log").read_text())
        except (ValueError, UnicodeError):
            pass
    receipt = {"argv": command, "cwd": str(ROOT), "started_at": start, "ended_at": now(),
        "elapsed_seconds": time.monotonic() - clock, "exit_code": exit_code,
        "collector_timeout": False, "collector_total_deadline_seconds": None,
        "collector_interruption": interrupted, "run_id": report.get("run_id", identified.name if identified else None),
        "status": report.get("overall_status", "ERROR"),
        "stdout_sha256": digest(directory / "stdout.log"), "stderr_sha256": digest(directory / "stderr.log")}
    atomic_json(directory / "command.json", receipt)
    return receipt, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="New, nonexistent calibration Full Archive")
    parser.add_argument("--gate", type=Path, required=True)
    args = parser.parse_args(argv)
    gate = json.loads(args.gate.read_text())
    required_policy = {"trials": 6, "order": ["single", "multi", "multi", "single", "single", "multi"],
        "provider": "gateway", "model": "gpt-5.6-terra", "reasoning_effort": "max",
        "completion_policy": "completion-aware", "agent_timeout": None,
        "request_budget": None, "parallel_trials": 1}
    if gate.get("mandatory_gate_result") != "PASS" or gate.get("calibration_configuration") != required_policy:
        raise ValueError("M1.1 admission Gate or frozen calibration protocol is incomplete")
    for name in ("R1", "R2", "isolation", "submission_fidelity", "operator_cancel", "export_verifier"):
        if gate.get("checks", {}).get(name) != "PASS":
            raise ValueError(f"Missing mandatory admission check: {name}")
    verify_freeze(gate)
    archive = args.archive.absolute()
    archive.mkdir(parents=True, exist_ok=False)
    atomic_json(archive / "PROTOCOL.json", {**required_policy, "gate_sha256": digest(args.gate),
        "recorded_at": now(), "scope": "Six-session exploratory calibration, not G0-G3 or statistical superiority"})
    from benchmark.manifest import private_config
    required = private_config("D")["expected_tests"]
    private_bytes = (ROOT / "evaluator/private_manifests/D.json").read_bytes()
    private_directory = archive / "frozen_private_manifests"
    private_directory.mkdir(mode=0o700)
    (private_directory / "D.json").write_bytes(private_bytes)
    protocol = json.loads((archive / "PROTOCOL.json").read_text())
    protocol["suite_expectations"] = [{"episode_id": "D", "expected_tests": required,
        "expected_test_count": len(required), "private_manifest_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "source_path": "frozen_private_manifests/D.json", "source_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "visibility": "MAINTAINER_PRIVATE; only test identities, not source assertions, enter Audit-Lite"}]
    atomic_json(archive / "PROTOCOL.json", protocol)
    records = []
    sessions = set()
    for index, mode in enumerate(required_policy["order"], 1):
        verify_freeze(gate)
        admission = {"trial": index, "agent_mode": mode, "checked_at": now(),
            "source_freeze": "PASS", "tls": tls_probe(gate["gateway_url"]),
            "host": host_observation(), "prior_trials_closed": len(records) == index - 1,
            "gate_sha256": digest(args.gate)}
        atomic_json(archive / f"trial-{index}.admission.json", admission)
        command = [sys.executable, "-m", "benchmark.cli", "--runs-root", str(archive / "runs"),
            "run-codex", "--episode", "D", "--variant", "v01", "--provider", "gateway",
            "--model", "gpt-5.6-terra", "--reasoning-effort", "max", "--completion-policy", "completion-aware",
            "--agent-timeout", "none", "--request-budget", "none", "--agent-mode", mode]
        receipt, report = collect_trial(archive / f"trial-{index}", command, archive / "runs")
        verify_freeze(gate)
        run_id = receipt["run_id"]
        metadata_path = archive / "runs" / str(run_id) / "runtime_metadata.json"
        metadata = json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
        run_directory = metadata_path.parent
        cleanup_checks = {"state_removed": not (run_directory / "codex-state").exists(),
            "process_tree_empty": metadata.get("resource_watchdog", {}).get("remaining_pids") == [],
            "cgroup_cleanup": metadata.get("resource_cgroup", {}).get("cleanup_complete") is True,
            "run_seal_present": (run_directory / "run_evidence_manifest.json").is_file()}
        cgroup_path = metadata.get("resource_cgroup", {}).get("path")
        cleanup_checks["cgroup_absent"] = bool(cgroup_path) and not Path(cgroup_path).exists()
        broker = metadata.get("model_broker", {})
        cleanup_checks["broker_handlers_stopped"] = broker.get("handler_cleanup_complete") is True
        cleanup_checks["broker_active_requests_zero"] = broker.get("active_requests") == 0
        for field in ("server_thread_stopped", "socket_unlinked", "token_revoked"):
            cleanup_checks["broker_" + field] = broker.get(field) is True
        if cleanup_checks["run_seal_present"]:
            seal = json.loads((run_directory / "run_evidence_manifest.json").read_text())
            cleanup_checks["run_seal_bytes_verified"] = seal.get("run_id") == run_id and all(
                not (run_directory / relative).is_symlink() and digest(run_directory / relative) == expected
                for relative, expected in seal.get("files", {}).items())
        else:
            cleanup_checks["run_seal_bytes_verified"] = False
        cleanup = {"status": "PASS" if all(cleanup_checks.values()) else "FAIL", "checks": cleanup_checks,
            "checked_at": now(), "scope": "Owned runtime resources and sealed local bytes, not arbitrary hostile attestation"}
        atomic_json(archive / f"trial-{index}.cleanup.json", cleanup)
        session = metadata.get("thread_id", "UNAVAILABLE")
        fresh = session != "UNAVAILABLE" and session not in sessions
        if session != "UNAVAILABLE":
            sessions.add(session)
        tests = report.get("test_results") or {}
        record = {"trial": index, "agent_mode": mode, "run_id": run_id, "command": receipt,
            "fresh_session_verified": fresh, "thread_id": session,
            **{key: report.get(key, "UNAVAILABLE") for key in ("runtime_status", "multi_agent_status",
                "isolation_status", "submission_integrity_status", "evaluation_status", "integration_status", "failure_kind")},
            "suite_complete": sorted(t["name"] for t in tests.get("tests", [])) == sorted(required),
            "test_counts": {key: tests.get(key) for key in ("collected", "passed", "failed", "errors", "skipped")},
            "required_test_count": len(required), "execution_errors": report.get("execution_errors", []),
            "recovery_coverage": report.get("recovery_coverage", {"status": "UNVERIFIED"}),
            "cleanup": cleanup, "single_agent_verification": metadata.get("single_agent_verification", "NOT_APPLICABLE"),
            "source_freeze_after": "PASS", "report_sha256": digest(metadata_path.parent / "evaluation_report.json") if run_id else "UNAVAILABLE"}
        records.append(record)
        atomic_json(archive / "PILOT_RESULTS.json", records)
        atomic_json(archive / "summary.json", {"protocol": required_policy, "attempted": len(records), "records": records,
            "denominator_policy": "All started sessions retained, including provider/runtime failures; no replacement by postmortem"})
        print(json.dumps({k: record[k] for k in ("trial", "agent_mode", "run_id", "runtime_status", "evaluation_status", "integration_status", "test_counts")}), flush=True)
        if receipt["collector_interruption"]["signal"] is not None:
            return 5
        if cleanup["status"] != "PASS":
            raise RuntimeError("Owned runtime cleanup/seal Gate failed; later sessions refused")
        if mode == "single" and metadata.get("single_agent_observed_child_count", 0) > 0:
            raise RuntimeError("Unexpected native child in single-agent condition; later sessions refused")
        if any("BLOCKED_SECURITY_GATE" in error for error in record["execution_errors"]):
            raise RuntimeError("Security gate failed; remaining live sessions refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
