"""Trusted D-V02 records and acknowledged-history Oracle.

The business process is stopped before inspection. No candidate import, audit(),
clock value, process ID or statement spelling determines these verdicts. Base
inventory accounting is the unchanged host Oracle; request records are read in
one SQLite snapshot. Constraint probes run only in disposable backups.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

from evaluator.episode_d_oracle import inspect_episode_d_database
from evaluator.oracle import _safe_file

ORACLE_VERSION = "1.1.1"
_COLUMNS = {
    "requests": {"request_id", "order_id", "sku", "quantity", "status", "current_token", "deadline", "receipt_json"},
    "request_claims": {"token", "request_id", "order_id", "sku", "quantity", "issued_tick", "issued_deadline"},
}
_PAYLOAD = ("order_id", "sku", "quantity")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")


def decimal_tick(value):
    if not isinstance(value, str) or _DECIMAL.fullmatch(value) is None:
        raise ValueError("Tick/deadline must be canonical nonnegative decimal TEXT")
    return int(value)


def _identifier(value):
    return isinstance(value, str) and bool(value) and not value.isspace()


def _strict_json(value):
    def object_pairs(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate receipt JSON key")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=object_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite receipt JSON")))


def public_request(row):
    """Host projection of persisted public fields, excluding opaque authority."""
    return {**{key: row[key] for key in ("request_id", *_PAYLOAD, "status")},
            "deadline": decimal_tick(row["deadline"]) if row["status"] == "PENDING" and row["deadline"] is not None else None,
            "receipt": row.get("receipt")}


def _request_constraint_probes(source, rows):
    probes = []
    for table, identity in (("requests", "request_id"), ("request_claims", "token")):
        if not rows[table]:
            probes.append({"name": table + ".empty", "availability": "NOT_APPLICABLE_EMPTY"})
            continue
        key = rows[table][0][identity]
        cases = [("quantity_positive", f'UPDATE "{table}" SET quantity=0 WHERE "{identity}"=?', (key,)),
                 ("inventory_foreign_key", f'UPDATE "{table}" SET sku=? WHERE "{identity}"=?', ("oracle-absent-sku", key)),
                 ("unique_identity", f'INSERT INTO "{table}" SELECT * FROM "{table}" WHERE "{identity}"=?', (key,))]
        if table == "requests":
            cases.append(("legal_status", "UPDATE requests SET status='UNDECLARED' WHERE request_id=?", (key,)))
        else:
            cases.append(("request_foreign_key", "UPDATE request_claims SET request_id=? WHERE token=?", ("oracle-absent-request", key)))
        for name, sql, params in cases:
            with closing(sqlite3.connect(":memory:", isolation_level=None)) as copy:
                source.backup(copy)
                copy.execute("PRAGMA foreign_keys=ON")
                copy.execute("PRAGMA trusted_schema=OFF")
                rejected, error = False, None
                before_rows = copy.execute(f'SELECT * FROM "{table}" ORDER BY "{identity}"').fetchall()
                try:
                    copy.execute("SAVEPOINT host_oracle_probe")
                    copy.execute(sql, params)
                    copy.execute("RELEASE host_oracle_probe")
                    # ON CONFLICT IGNORE and equivalent rejecting triggers are
                    # valid enforcement when the invalid write has no effect.
                    rejected = copy.execute(f'SELECT * FROM "{table}" ORDER BY "{identity}"').fetchall() == before_rows
                except sqlite3.DatabaseError as exception:
                    rejected, error = True, type(exception).__name__
                probes.append({"name": table + "." + name, "availability": "AVAILABLE", "rejected": rejected, "error": error})
    return probes


def inspect_episode_d_v02_database(db_path: Path, *, expected_stock: Mapping[str, int],
                                  data_dir: Path, expected_identity=None,
                                  expected_requests: Mapping[str, Mapping | None] | None = None,
                                  expected_orders: Mapping[str, Mapping | None] | None = None) -> dict:
    audit = inspect_episode_d_database(db_path, expected_stock=expected_stock, data_dir=data_dir,
                                      expected_orders=expected_orders)
    audit.update(episode_d_v02_oracle_version=ORACLE_VERSION, requests=[], request_claims=[],
                 request_schema={}, request_constraint_probes=[], request_records_available=False)
    violations = audit["violations"]
    path = Path(db_path).absolute()
    try:
        _safe_file(path, Path(data_dir))
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        audit["database_identity"] = {"device": identity[0], "inode": identity[1]}
        if expected_identity is not None and identity != tuple(expected_identity):
            raise ValueError("Database inode differs from trusted supervisor")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5,
                                     isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("BEGIN")
            for table, columns in _COLUMNS.items():
                definition = connection.execute("SELECT type,sql FROM sqlite_schema WHERE name=?", (table,)).fetchone()
                if definition is None or definition["type"] != "table":
                    raise ValueError("Missing public base table: " + table)
                actual = {row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')}
                if not columns <= actual:
                    raise ValueError("Missing public record columns: " + table)
                foreign_keys = [dict(row) for row in connection.execute(f'PRAGMA foreign_key_list("{table}")')]
                primary = {row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")') if row["pk"]}
                identity_column = "request_id" if table == "requests" else "token"
                if primary != {identity_column}:
                    violations.append("Public identity is not its single primary key: " + table)
                required_fks = [("sku", "inventory", "sku")]
                if table == "request_claims":
                    required_fks.append(("request_id", "requests", "request_id"))
                for field, target, target_field in required_fks:
                    if not any(row["from"] == field and row["table"] == target and row["to"] == target_field for row in foreign_keys):
                        violations.append(f"Missing public record foreign key: {table}.{field}")
                audit["request_schema"][table] = {"sql": definition["sql"], "columns": sorted(actual),
                                                   "primary_key": sorted(primary), "foreign_keys": foreign_keys}
                audit[table] = [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY "{identity_column}"')]
            # Backup is performed after the read snapshot finishes, with workers
            # stopped. Avoid SQLite backup retrying its own active read txn.
            connection.execute("COMMIT")
            audit["request_constraint_probes"] = _request_constraint_probes(connection, audit)
        if (path.stat().st_dev, path.stat().st_ino) != identity:
            raise ValueError("Database replaced during independent inspection")
        for probe in audit["request_constraint_probes"]:
            if probe.get("availability") == "AVAILABLE" and probe["rejected"] is not True:
                violations.append("Database accepted invalid public record: " + probe["name"])
        requests = {row["request_id"]: row for row in audit["requests"]}
        claims = {row["token"]: row for row in audit["request_claims"]}
        orders = {row["order_id"]: row for row in audit["orders"]}
        reserved = {row["order_id"] for row in audit["ledger"] if row["action"] == "reserve"}
        for claim in claims.values():
            token, request_id = claim["token"], claim["request_id"]
            if not _identifier(token) or not _identifier(request_id):
                violations.append("Invalid issuance identity")
            request = requests.get(request_id)
            if request is None or any(claim[key] != request[key] for key in _PAYLOAD):
                violations.append("Claim history payload differs from intent: " + str(token))
            if type(claim["quantity"]) is not int or claim["quantity"] <= 0:
                violations.append("Invalid claim quantity: " + str(token))
            try:
                issued, deadline = decimal_tick(claim["issued_tick"]), decimal_tick(claim["issued_deadline"])
                if deadline <= issued:
                    violations.append("Claim issuance deadline does not follow issue: " + str(token))
            except (ValueError, TypeError):
                violations.append("Malformed claim decimal history: " + str(token))
        for request in requests.values():
            request_id = request["request_id"]
            if not all(_identifier(request[key]) for key in ("request_id", "order_id", "sku")):
                violations.append("Invalid request payload identity: " + str(request_id))
            if type(request["quantity"]) is not int or request["quantity"] <= 0:
                violations.append("Invalid request quantity: " + str(request_id))
            if request["status"] not in {"PENDING", "COMPLETED", "CANCELLED"}:
                violations.append("Invalid persisted request status: " + str(request_id))
            token, deadline = request["current_token"], request["deadline"]
            if (token is None) != (deadline is None):
                violations.append("Incomplete current authority: " + str(request_id))
            if token is not None:
                claim = claims.get(token)
                if claim is None or claim["request_id"] != request_id:
                    violations.append("Current token has no corresponding claim history: " + str(request_id))
                try:
                    current = decimal_tick(deadline)
                    if claim is not None and current < decimal_tick(claim["issued_deadline"]):
                        violations.append("Current deadline precedes issuance: " + str(request_id))
                except (ValueError, TypeError):
                    violations.append("Malformed current deadline: " + str(request_id))
            request["receipt"] = None
            if request["status"] == "PENDING":
                if request["receipt_json"] is not None:
                    violations.append("Pending request contains terminal receipt: " + str(request_id))
                continue
            try:
                receipt = _strict_json(request["receipt_json"])
                if not isinstance(receipt, dict) or not {"outcome", "request_id", *_PAYLOAD} <= receipt.keys():
                    raise ValueError("Missing persisted receipt fields")
                if any(type(receipt[key]) is not type(request[key]) or receipt[key] != request[key]
                       for key in ("request_id", *_PAYLOAD)):
                    raise ValueError("Receipt payload differs from intent")
                allowed = {"COMPLETE_RESERVED", "COMPLETE_DISCOVERED_CANCELLED"} if request["status"] == "COMPLETED" else {"REQUEST_CANCELLED"}
                if receipt["outcome"] not in allowed:
                    raise ValueError("Receipt outcome differs from terminal state")
                request["receipt"] = receipt
                if request["status"] == "COMPLETED":
                    order = orders.get(request["order_id"])
                    if order is None or any(order[key] != request[key] for key in _PAYLOAD):
                        raise ValueError("Completed receipt has no matching persisted order")
                    if receipt["outcome"] == "COMPLETE_RESERVED" and request["order_id"] not in reserved:
                        raise ValueError("Successful reservation receipt has no durable reserve ledger")
                    if receipt["outcome"] == "COMPLETE_DISCOVERED_CANCELLED" and order["status"] != "cancelled":
                        raise ValueError("Cancelled discovery receipt refers to noncancelled order")
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                violations.append(f"Invalid terminal receipt {request_id}: {error}")
        for request_id, expected in (expected_requests or {}).items():
            actual = requests.get(request_id)
            if expected is None:
                if actual is not None:
                    violations.append("Request expected absent is persisted: " + request_id)
            elif actual is None or any(type(actual.get(key)) is not type(value) or actual.get(key) != value for key, value in expected.items()):
                violations.append("Persisted request differs from trusted expectation: " + request_id)
        audit["request_records_available"] = True
    except (OSError, ValueError, TypeError, sqlite3.Error) as error:
        violations.append(f"Request Oracle storage error: {type(error).__name__}: {error}")
    audit["consistent"] = not violations
    return audit


def _typed_receipt_equal(left, right):
    # Canonical JSON preserves bool/int/float distinctions that Python object
    # equality conflates. Key ordering and harmless JSON whitespace are free.
    return json.dumps(left, sort_keys=True, allow_nan=False, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, allow_nan=False, separators=(",", ":"))


def inspect_acknowledged_history(snapshots: Sequence[Mapping]) -> dict:
    """Check immutable records across host snapshots following real RPC ACKs.

    Not a linearizability guess for overlapping operations: captures are made
    at sequential acknowledged boundaries. Each initialized DB has its own
    history. Receipt comparisons use parsed typed values, not JSON key order.
    """
    violations, previous_requests, previous_claims = [], {}, {}
    for index, snapshot in enumerate(snapshots):
        audit = snapshot.get("audit", {})
        if not audit.get("request_records_available") or not audit.get("consistent"):
            violations.append(f"Snapshot lacks consistent independently read records: {index}")
        requests = {row["request_id"]: row for row in audit.get("requests", [])}
        claims = {row["token"]: row for row in audit.get("request_claims", [])}
        for request_id, old in previous_requests.items():
            new = requests.get(request_id)
            if new is None or any(new[key] != old[key] for key in _PAYLOAD):
                violations.append(f"Request disappeared or changed payload at {index}: {request_id}")
            elif old["status"] != "PENDING" and (new["status"] != old["status"] or not _typed_receipt_equal(new.get("receipt"), old.get("receipt"))):
                violations.append(f"Acknowledged terminal state/receipt mutated at {index}: {request_id}")
        for token, old in previous_claims.items():
            new = claims.get(token)
            if new is None or any(type(new.get(key)) is not type(old[key]) or new.get(key) != old[key]
                                  for key in ("token", "request_id", *_PAYLOAD, "issued_tick", "issued_deadline")):
                violations.append(f"Issuance history disappeared or mutated at {index}: {token}")
        previous_requests, previous_claims = requests, claims
    return {"oracle_version": ORACLE_VERSION, "snapshot_count": len(snapshots),
            "consistent": not violations, "violations": violations,
            "authority": "TRUSTED_HOST_ACK_BOUNDARIES; RAW_SQLITE_BASE_TABLES"}


def require_recovery_evidence(record, topology, *, method, label, readonly_stale=False):
    """Return verifiable proof or raise in hidden fixture setup (JUnit ERROR)."""
    if type(readonly_stale) is not bool or readonly_stale and (method, label) != ("complete_request", "before_response"):
        raise RecoveryEvidenceUnavailable("RECOVERY_EVIDENCE_UNVERIFIED: invalid readonly stale evidence scope")
    event = record.get("event", {})
    metadata = event.get("metadata", {})
    kill = record.get("kill") or {}
    identity = event.get("identity") or {}
    host_pid = event.get("host_pid", identity.get("host_pid"))
    database = topology.get("shared_database", {})
    reasons = []
    if record.get("availability") != "AVAILABLE" or record.get("label") != label:
        reasons.append("requested generic observer boundary unavailable")
    if metadata.get("method") != method:
        reasons.append("observed method differs from requested method")
    if (not kill or kill.get("signal") != "SIGKILL" or kill.get("worker_pidfd_exited") is not True
            or kill.get("mechanism") != "pidfd_send_signal" or type(host_pid) is not int
            or kill.get("identity", {}).get("host_pid") != host_pid):
        reasons.append("owned kernel PIDFD kill/exit proof unavailable")
    if record.get("request_outcome", {}).get("response_available") is not False:
        reasons.append("response absence not established")
    if label in {"before_commit", "transaction_committed"} and not (metadata.get("target_database") is True and metadata.get("write_observed") is True):
        reasons.append("actual target SQLite write/commit proof unavailable")
    matching = [row for row in topology.get("database_fd_witnesses", [])
                if (row.get("method") == method or readonly_stale and row.get("method") == "claim_request") and row.get("availability") == "AVAILABLE"
                and row.get("identity", {}).get("host_pid") == host_pid
                and any(fd.get("device") == database.get("device") and fd.get("inode") == database.get("inode")
                        for fd in row.get("matching_fds", []))]
    if not matching:
        reasons.append("owned worker has no target database FD witness")
    if reasons:
        raise RecoveryEvidenceUnavailable("RECOVERY_EVIDENCE_UNVERIFIED: " + "; ".join(reasons))
    return {"verified": True, "method": method, "label": label, "event": event,
            "kill": kill, "fd_witnesses": matching, "readonly_stale_allowed": readonly_stale,
            "fd_witness_scope": "SAME_KERNEL_GENERATION_SHARED_DB" if readonly_stale else "SAME_KERNEL_GENERATION_METHOD_SHARED_DB",
            "authority": "TRUSTED_KERNEL_PIDFD_FD_SQLITE_OBSERVER"}


class RecoveryEvidenceUnavailable(RuntimeError):
    """Missing observability is infrastructure ERROR, never task PASS/FAIL."""


def inspect_publication_boundary(before: Mapping, after: Mapping, *, request_id: str) -> dict:
    """Check complete publication following a quiescent claim ACK.

    A newly created order or a new reservation of a matching, previously
    unreserved order cannot commit separately from its terminal request receipt.
    A preexisting reservation is not a new effect of this call. A commit with
    no new business effect may leave the request pending. No SQL transaction
    count or private helper is prescribed. A previously acknowledged matching
    unreserved order must survive this sole-complete-writer window with the
    same typed payload; complete may leave it created/none or reserve it, but
    cannot delete, rewrite or independently cancel it before publication.
    The caller supplies independently captured before/after base records and
    establishes that this is the sole business call between those captures.
    """
    violations = []
    old = next((row for row in before.get("requests", []) if row["request_id"] == request_id), None)
    new = next((row for row in after.get("requests", []) if row["request_id"] == request_id), None)
    applicable = old is not None and old["status"] == "PENDING"
    if not before.get("consistent") or not after.get("consistent"):
        violations.append("Publication boundary lacks valid independent before/after records")
    effect = False
    publication_kind = None
    new_reserve_rows = []
    if applicable:
        order_id = old["order_id"]
        old_order = next((row for row in before.get("orders", []) if row["order_id"] == order_id), None)
        new_order = next((row for row in after.get("orders", []) if row["order_id"] == order_id), None)
        old_ledger = [row for row in before.get("ledger", []) if row["order_id"] == order_id]
        new_ledger = [row for row in after.get("ledger", []) if row["order_id"] == order_id]
        new_reserve_rows = [row for row in new_ledger if row["action"] == "reserve"
                            and not any(_typed_receipt_equal(row, prior) for prior in old_ledger)]
        absent_order = old_order is None and not old_ledger
        existing_unreserved = (old_order is not None and old_order["status"] == "created"
            and old_order["reservation_state"] == "none"
            and all(type(old_order[key]) is type(old[key]) and old_order[key] == old[key] for key in _PAYLOAD)
            and not any(row["action"] == "reserve" for row in old_ledger))
        applicable = absent_order or existing_unreserved
        if absent_order:
            publication_kind = "NEW_ORDER"
            effect = new_order is not None or bool(new_ledger)
        elif existing_unreserved:
            publication_kind = "EXISTING_UNRESERVED_ORDER"
            if new_order is None:
                violations.append("Previously acknowledged unreserved order disappeared during complete: " + order_id)
            elif any(type(new_order.get(key)) is not type(old_order[key]) or new_order.get(key) != old_order[key]
                     for key in _PAYLOAD):
                violations.append("Previously acknowledged unreserved order changed typed payload during complete: " + order_id)
            elif (new_order["status"], new_order["reservation_state"]) not in {("created", "none"), ("reserved", "active")}:
                violations.append("Previously acknowledged unreserved order changed lifecycle outside complete: " + order_id)
            effect = bool(new_reserve_rows) or (new_order is not None and new_order["reservation_state"] == "active")
        if applicable and effect:
            receipt = None if new is None else new.get("receipt")
            terminal = (new is not None and new["status"] == "COMPLETED" and isinstance(receipt, dict)
                and receipt.get("outcome") == "COMPLETE_RESERVED"
                and all(key in receipt and type(receipt[key]) is type(old[key]) and receipt[key] == old[key]
                        for key in ("request_id", *_PAYLOAD)))
            if not terminal:
                violations.append("New complete business records committed without terminal request receipt: " + request_id)
    return {"oracle_version": ORACLE_VERSION, "consistent": not violations,
            "applicable": applicable, "request_id": request_id, "violations": violations,
            "publication_kind": publication_kind, "business_effect_observed": effect,
            "new_reserve_ledger_rows": new_reserve_rows,
            "authority": "TRUSTED_QUIESCENT_CLAIM_ACK_AND_RAW_SQLITE_CRASH_SNAPSHOTS"}
