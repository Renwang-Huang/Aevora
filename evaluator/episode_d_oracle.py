"""Trusted storage, response and write-witness audit for shared-worker tasks.

No candidate modules are imported here.  Candidate responses are checked
against independently observed storage; topology identities must come from
the trusted supervisor, rather than a candidate-provided PID or ``audit()``.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from evaluator.oracle import _safe_file, inspect_database


ORACLE_VERSION = "1.0.0"
_BUSINESS_ERRORS = frozenset({
    "InsufficientInventory", "InvalidInput", "OrderConflict", "OrderNotFound",
    "InventoryNotFound", "InvalidOrderState", "FixtureConflict",
})


def _valid_response_state(method: str, params: Mapping, row: Mapping) -> bool:
    """Check the returned API state without comparing later mutable DB state."""
    status, reservation = row.get("status"), row.get("reservation_state")
    if not isinstance(status, str) or not isinstance(reservation, str):
        return False
    if type(row.get("quantity")) is not int or row["quantity"] <= 0:
        return False
    state = (status, reservation)
    cancelled = {("cancelled", "none"), ("cancelled", "released")}
    if method in {"cancel_order", "release_inventory"}:
        return state in cancelled
    if method == "reserve_inventory":
        return state == ("reserved", "active")
    if method == "create_order":
        reserve = params.get("reserve", True)
        if type(reserve) is not bool:
            return False
        allowed = cancelled | {("reserved", "active")}
        if not reserve:
            allowed.add(("created", "none"))
        return state in allowed
    return False


def _file_fingerprints(path: Path) -> dict:
    result = {}
    for suffix in ("", "-journal", "-wal", "-shm"):
        file = Path(str(path) + suffix)
        if not file.exists():
            result[suffix or "database"] = None
            continue
        descriptor = os.open(file, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ValueError("Storage fingerprint requires ordinary single-link files")
            digest = hashlib.sha256()
            while chunk := os.read(descriptor, 1024 * 1024):
                digest.update(chunk)
            after = os.fstat(descriptor)
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise ValueError("Storage changed during trusted fingerprint collection")
            result[suffix or "database"] = {
                "sha256": digest.hexdigest(), "size": after.st_size,
                "st_dev": after.st_dev, "st_ino": after.st_ino,
            }
        finally:
            os.close(descriptor)
    return result


def recover_episode_d_database(db_path: Path, *, data_dir: Path,
                               workers_stopped: bool,
                               expected_identity: tuple[int, int] | None = None) -> dict:
    """Allow SQLite itself to recover its journal after all workers are stopped.

    This is an explicit trusted recovery step before the read-only row oracle.
    It does not create databases, discard journals, rewrite business rows, or
    run candidate code.  The caller must establish process termination before
    passing ``workers_stopped=True``.  Both storage snapshots are archived.
    """
    result = {
        "episode_d_oracle_version": ORACLE_VERSION, "status": "ERROR",
        "workers_stopped": workers_stopped, "before": None, "after": None,
        "integrity_check": [], "error": None,
    }
    try:
        if workers_stopped is not True:
            raise ValueError("Trusted SQLite recovery requires all workers stopped")
        path = Path(db_path).absolute()
        _safe_file(path, Path(data_dir))
        identity = path.stat()
        if expected_identity is not None and (identity.st_dev, identity.st_ino) != expected_identity:
            raise ValueError("Database identity differs from the supervisor's shared file")
        result["before"] = _file_fingerprints(path)
        # mode=rw refuses to create a missing file.  trusted_schema suppresses
        # execution of unsafe schema functions during the integrity query.
        with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
                                     timeout=5.0, isolation_level=None)) as connection:
            connection.execute("PRAGMA trusted_schema = OFF")
            result["integrity_check"] = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        _safe_file(path, Path(data_dir))
        result["after"] = _file_fingerprints(path)
        if (path.stat().st_dev, path.stat().st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError("Database identity changed during trusted recovery")
        if result["integrity_check"] != ["ok"]:
            raise ValueError("SQLite recovery integrity_check failed")
        result["status"] = ("RECOVERED" if result["before"] != result["after"]
                            else "NO_STORAGE_CHANGE")
    except (OSError, ValueError, sqlite3.Error) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def inspect_episode_d_database(
        db_path: Path, *, expected_stock: Mapping[str, int], data_dir: Path,
        requests: list[dict] | None = None, results: list[dict] | None = None,
        required_worker_ids: Iterable[int] | None = None,
        expected_orders: Mapping[str, Mapping | None] | None = None,
        expected_order_ids: Iterable[str] | None = None) -> dict:
    """Audit rows and optional supervisor results without a repair-strategy test.

    ``requests`` use ordinary ``{method, params}`` operations.  Supervisor
    result envelopes contain ``index`` and trusted ``worker_index``.  Positive
    write witnesses require a unique create request assigned to that worker,
    a successful matching response and the corresponding durable order and,
    when reserved, reserve ledger.  Duplicate-ID retries do not count as new
    writes by several workers.  A separate ample-stock phase should request
    witnesses; capacity-exhaustion winners need not be evenly distributed.
    """
    audit = inspect_database(db_path, expected_stock=expected_stock, data_dir=data_dir)
    audit["episode_d_oracle_version"] = ORACLE_VERSION
    violations = audit["violations"]
    orders = {row["order_id"]: row for row in audit["orders"]}
    reserve_ids = {row["order_id"] for row in audit["ledger"] if row["action"] == "reserve"}
    response_checks = {
        "available": requests is not None and results is not None, "checked": 0,
        "successful": 0, "failed": 0, "unique_successful_order_ids": [],
        "all_match": False,
    }
    audit["response_checks"] = response_checks
    witnesses: dict[int, set[str]] = defaultdict(set)

    if expected_order_ids is not None and set(orders) != set(expected_order_ids):
        violations.append("Persisted order identity set differs from trusted expectations")
    for order_id, expected in (expected_orders or {}).items():
        actual = orders.get(order_id)
        if expected is None:
            if actual is not None:
                violations.append(f"Order expected to be absent is persisted: {order_id}")
        elif actual is None or any(actual.get(key) != value for key, value in expected.items()):
            violations.append(f"Persisted order differs from trusted expectation: {order_id}")

    if requests is not None or results is not None:
        if (not isinstance(requests, list) or not isinstance(results, list)
                or len(requests) != len(results) or len(requests) > 1000):
            violations.append("Supervisor request/result collection is missing or has unequal counts")
        else:
            unique_create_ids = Counter(
                operation.get("params", {}).get("order_id")
                for operation in requests if isinstance(operation, dict)
                and operation.get("method") == "create_order"
                and isinstance(operation.get("params", {}), dict)
                and isinstance(operation.get("params", {}).get("order_id"), str)
            )
            observed_indexes = set()
            successful_ids = set()
            starting_violations = len(violations)
            for envelope in results:
                if not isinstance(envelope, dict):
                    violations.append("Supervisor result is not an object")
                    continue
                index = envelope.get("index")
                if (type(index) is not int or not 0 <= index < len(requests)
                        or index in observed_indexes):
                    violations.append("Supervisor result index is invalid or duplicated")
                    continue
                observed_indexes.add(index)
                operation = requests[index]
                if (not isinstance(operation, dict)
                        or not isinstance(operation.get("params", {}), dict)):
                    violations.append(f"Supervisor request is invalid: {index}")
                    continue
                params = operation.get("params", {})
                method = operation.get("method")
                response_checks["checked"] += 1
                if envelope.get("ok") is False:
                    response_checks["failed"] += 1
                    error = envelope.get("error")
                    if not isinstance(error, dict) or error.get("type") not in _BUSINESS_ERRORS:
                        violations.append(f"Unexpected operation exception instead of a business result: {index}")
                    continue
                if envelope.get("ok") is not True:
                    violations.append(f"Operation result lacks a boolean business outcome: {index}")
                    continue
                response_checks["successful"] += 1
                if method not in {"create_order", "reserve_inventory", "cancel_order", "release_inventory"}:
                    continue
                row = envelope.get("result")
                order_id = params.get("order_id")
                if not isinstance(order_id, str):
                    violations.append(f"Successful response refers to an invalid order identity: {index}")
                    continue
                persisted = orders.get(order_id)
                if (not isinstance(row, dict) or row.get("order_id") != order_id or persisted is None):
                    violations.append(f"Successful response has no matching durable order: {index}")
                    continue
                if any(row.get(key) != persisted[key] for key in ("order_id", "sku", "quantity")):
                    violations.append(f"Successful response contents differ from storage: {index}")
                    continue
                if not _valid_response_state(method, params, row):
                    violations.append(f"Successful response has an invalid state for its API operation: {index}")
                    continue
                if method == "create_order" and any(
                        row.get(key) != params.get(key) for key in ("sku", "quantity")):
                    violations.append(f"Create response contents differ from its request: {index}")
                    continue
                successful_ids.add(order_id)
                if method == "create_order" and unique_create_ids[order_id] == 1:
                    # A cancelled ID can be returned by an idempotent create.
                    # It is not a new write witness and may never have reserved.
                    if row["status"] == "cancelled":
                        continue
                    if row["reservation_state"] == "active" and order_id not in reserve_ids:
                        violations.append(f"Successful reserved create has no durable reserve ledger: {index}")
                        continue
                    worker_id = envelope.get("worker_index")
                    if type(worker_id) is int:
                        witnesses[worker_id].add(order_id)
            if observed_indexes != set(range(len(requests))):
                violations.append("Supervisor result collection does not cover every operation")
            response_checks["unique_successful_order_ids"] = sorted(successful_ids)
            response_checks["all_match"] = (len(violations) == starting_violations)

    required = sorted(set(required_worker_ids or ()))
    missing = [worker for worker in required if not witnesses[worker]]
    audit["write_witness"] = {
        "source": "trusted_supervisor_assignment_and_independent_database",
        "required_worker_ids": required,
        "per_worker_order_ids": {str(worker): sorted(ids) for worker, ids in sorted(witnesses.items())},
        "missing_worker_ids": missing,
        "verified": not missing if required else None,
    }
    if missing:
        violations.append(f"Workers lack an independent durable write witness: {missing}")
    audit["consistent"] = not violations
    return audit
