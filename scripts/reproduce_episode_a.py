#!/usr/bin/env python3
"""One controlled Episode A batch with real threads and a host database audit.

This is a fault reproducer, not the complete independent hidden-test suite. Run
the normal ``orderflow evaluate --episode A`` command for full Episode grading.
Every invocation creates a fresh candidate/database and preserves its evidence.
"""

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.persistence import SQLITE_BUSY_TIMEOUT_SECONDS
from benchmark.registry import get_episode
from benchmark.runner import apply_patch, copy_app
from evaluator.oracle import inspect_database
from evaluator.rpc import BusinessRPC


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def source_digest(app):
    digest = hashlib.sha256()
    for path in sorted(app.rglob("*.py")):
        digest.update(str(path.relative_to(app)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@contextmanager
def execution_deadline(seconds):
    """Bound even an invalid/hanging candidate on this Linux sandbox platform."""
    def expire(signum, frame):
        raise TimeoutError(f"Reproduction exceeded {seconds:g} seconds")

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path,
                        help="app directory, workspace containing app/, or unified .diff patch")
    parser.add_argument("--stock", type=int, default=50)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--workers", type=int, default=200)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    result = parser.parse_args(argv)
    if result.stock < 0 or result.quantity <= 0:
        parser.error("stock must be nonnegative and quantity must be positive")
    if not 1 <= result.requests <= 1000 or not 1 <= result.workers <= 256:
        parser.error("requests must be 1..1000 and workers must be 1..256")
    if not 0 < result.timeout_seconds <= 300:
        parser.error("timeout-seconds must be positive and at most 300")
    return result


def main(argv=None):
    args = arguments(argv)
    run_id = str(uuid4())
    archive = ROOT / "runs" / "reproductions" / run_id
    archive.mkdir(parents=True)
    candidate = archive / "candidate"
    data_dir = archive / "data"
    registration = get_episode("A")
    expected_success = min(args.requests, args.stock // args.quantity)
    expected_reserved = expected_success * args.quantity
    report = {
        "schema_version": "1.0.0", "episode_id": "A", "run_id": run_id,
        "scope": "single_controlled_batch_reproducer",
        "full_hidden_evaluator": False, "test_results": None,
        "status": "ERROR", "started_at": timestamp(), "ended_at": None,
        "command": {"executable": sys.executable, "argv": sys.argv},
        "scenario_variant": registration.default_variant,
        "fixture_version": registration.fixture_version,
        "parameters": {"stock": args.stock, "requests": args.requests,
                       "workers": args.workers, "quantity": args.quantity,
                       "checkpoint_timeout_seconds": 2.0,
                       "execution_timeout_seconds": args.timeout_seconds},
        "topology": {"processes": 1, "concurrency": "threads", "storage": "SQLite"},
        "expected": {"successful_orders": expected_success,
                     "insufficient_orders": args.requests - expected_success,
                     "available": args.stock - expected_reserved,
                     "reserved": expected_reserved},
        "submission": None, "batch": None, "database_oracle": None,
        "checks": {}, "execution_errors": [],
        "runtime": {"python": sys.version, "sqlite": sqlite3.sqlite_version,
                    "sqlite_busy_timeout_seconds": SQLITE_BUSY_TIMEOUT_SECONDS,
                    "isolation": "bubblewrap", "network_isolated": False},
        "fingerprints": {},
        "artifacts": {"directory": str(archive.relative_to(ROOT)),
                      "worker_log": str((archive / "worker.log").relative_to(ROOT)),
                      "database": str((data_dir / "business.sqlite").relative_to(ROOT)),
                      "summary": str((archive / "summary.stdout.json").relative_to(ROOT)),
                      "report": str((archive / "reproduction.json").relative_to(ROOT))},
    }
    for filename in ("scripts/reproduce_episode_a.py", "evaluator/worker.py", "evaluator/oracle.py"):
        report["fingerprints"][filename] = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
    rpc = None
    try:
        submission = args.submission.absolute() if args.submission else None
        if submission is None:
            registration.build(candidate)
            report["submission"] = {"kind": "default_buggy_fixture", "reference": None}
        elif submission.is_dir():
            candidate.mkdir()
            copy_app(submission, candidate / "app")
            report["submission"] = {"kind": "workspace", "reference": str(submission)}
        else:
            registration.build(candidate)
            patch = archive / "patch.diff"
            patch.write_bytes(submission.read_bytes())
            apply_patch(candidate, patch)
            report["submission"] = {"kind": "patch", "reference": str(submission),
                                    "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
            report["artifacts"]["patch"] = str(patch.relative_to(ROOT))
        report["submission"]["candidate_sha256"] = source_digest(candidate / "app")
        operations = [{"method": "create_order", "params": {
            "order_id": f"purchase-{index}", "sku": "widget", "quantity": args.quantity,
        }} for index in range(args.requests)]
        rpc = BusinessRPC(candidate, data_dir, archive / "worker.log")
        with execution_deadline(args.timeout_seconds):
            rpc.start()
            rpc.call("initialize", stock={"widget": args.stock}, reset=True)
            report["batch"] = rpc.batch(
                operations, max_workers=args.workers, synchronize_start=True,
                checkpoint={"label": "inventory_read", "timeout_seconds": 2.0},
            )
    except Exception as error:
        report["execution_errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if rpc is not None:
            try:
                rpc.close()
            except Exception as error:
                report["execution_errors"].append(f"Worker close error: {type(error).__name__}: {error}")

    # Host storage inspection begins only after the candidate worker has stopped.
    oracle = inspect_database(data_dir / "business.sqlite",
                              expected_stock={"widget": args.stock}, data_dir=data_dir)
    report["database_oracle"] = oracle
    batch = report["batch"]
    if batch is not None:
        results = batch["results"]
        successful = [result for result in results if result["ok"]]
        rejected = [result for result in results if not result["ok"]]
        errors = Counter(result["error"]["type"] for result in rejected)
        inventory = next((row for row in oracle["inventory"] if row["sku"] == "widget"), None)
        active_orders = [row for row in oracle["orders"] if row["reservation_state"] == "active"]
        report["observed"] = {
            "successful_orders": len(successful), "unsuccessful_orders": len(rejected),
            "error_types": dict(errors), "inventory": inventory,
            "active_order_count": len(active_orders), "ledger_entries": len(oracle["ledger"]),
        }
        report["checks"] = {
            "all_requests_have_results": len(results) == args.requests,
            "results_in_request_order": [result["index"] for result in results] == list(range(args.requests)),
            "one_process": {result["pid"] for result in results} == {batch["execution"]["pid"]},
            "concurrent_threads": (args.requests == 1 or args.workers == 1 or (
                len(batch["execution"]["thread_ids"]) > 1 and batch["execution"]["max_active"] > 1)),
            "successful_order_count": len(successful) == expected_success,
            "insufficient_order_count": errors.get("InsufficientInventory", 0) == args.requests - expected_success,
            "only_expected_business_errors": not (set(errors) - {"InsufficientInventory"}),
            "independent_database_consistent": oracle["consistent"],
            "available_quantity": inventory is not None and inventory["available"] == args.stock - expected_reserved,
            "reserved_quantity": inventory is not None and inventory["reserved"] == expected_reserved,
            "active_orders_match_successes": len(active_orders) == len(successful),
            "stored_active_quantity": sum(row["quantity"] for row in active_orders) == expected_reserved,
        }
        if set(errors) - {"InsufficientInventory"}:
            report["execution_errors"].append(f"Unexpected operation errors: {dict(errors)}")
        report["status"] = "PASS" if all(report["checks"].values()) else "FAIL"
    if report["execution_errors"]:
        report["status"] = "ERROR"
    report["ended_at"] = timestamp()
    exit_code = {"PASS": 0, "FAIL": 1, "ERROR": 2}[report["status"]]
    report["exit_code"] = exit_code
    (archive / "reproduction.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    execution = batch["execution"] if batch else None
    gate = execution["checkpoint"] if execution else None
    summary = {
        "scope": report["scope"], "full_hidden_evaluator": False,
        "run_id": run_id, "status": report["status"], "exit_code": exit_code,
        "expected": report["expected"], "observed": report.get("observed"),
        "concurrency": {"pid": execution["pid"], "thread_count": len(execution["thread_ids"]),
                        "max_active": execution["max_active"],
                        "checkpoint": {key: gate[key] for key in ("arrivals", "parties", "released_by")}
                                      if gate else None} if execution else None,
        "oracle_violations": oracle["violations"],
        "execution_errors": report["execution_errors"],
        "report": str((archive / "reproduction.json").relative_to(ROOT)),
    }
    output = json.dumps(summary, indent=2)
    (archive / "summary.stdout.json").write_text(output + "\n")
    print(output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
