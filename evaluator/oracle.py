"""Host-only SQLite truth, independent of the candidate's ``audit`` method.

Call this after the worker has stopped. The evaluator chooses expected_stock;
neither a candidate response nor its stored initial_stock defines the fixture.
"""

from collections import Counter
from collections.abc import Mapping
from contextlib import closing
import hashlib
from pathlib import Path
import re
import sqlite3
import stat
from uuid import uuid4


ORACLE_VERSION = "1.0.0"
_COLUMNS = {
    "inventory": {"sku", "initial_stock", "available", "reserved", "committed"},
    "orders": {"order_id", "sku", "quantity", "status", "reservation_state"},
    "inventory_ledger": {
        "entry_id", "order_id", "sku", "action", "quantity", "available_delta",
        "reserved_delta", "committed_delta",
    },
}


def _constraint_probes(connection: sqlite3.Connection) -> list[dict]:
    """Exercise schema semantics exclusively in disposable in-memory backups.

    Each probe starts from the same source database. A valid fixture makes the
    invalid write independent of the candidate's current rows. Releasing the
    outer SAVEPOINT also checks deferred foreign keys; accepted writes affect
    only a disposable copy. Equivalent CHECK expressions and SQLite triggers
    can reject a probe without matching any specific SQL spelling.
    """
    suffix = uuid4().hex
    sku = f"oracle-sku-{suffix}"
    order_id = f"oracle-order-{suffix}"
    absent = f"oracle-absent-{suffix}"
    probes = [
        ("inventory.available_nonnegative",
         "UPDATE inventory SET available = -1, reserved = 3, committed = 0 WHERE sku = ?", (sku,)),
        ("inventory.reserved_nonnegative",
         "UPDATE inventory SET available = 3, reserved = -1, committed = 0 WHERE sku = ?", (sku,)),
        ("inventory.committed_nonnegative",
         "UPDATE inventory SET available = 3, reserved = 0, committed = -1 WHERE sku = ?", (sku,)),
        ("inventory.initial_stock_nonnegative",
         "UPDATE inventory SET initial_stock = -1, available = -1, reserved = 0, committed = 0 WHERE sku = ?",
         (sku,)),
        ("inventory.stock_conservation",
         "UPDATE inventory SET available = 2, reserved = 1, committed = 0 WHERE sku = ?", (sku,)),
        ("inventory.unique_sku",
         "INSERT INTO inventory(sku, initial_stock, available, reserved, committed) VALUES (?, 2, 2, 0, 0)",
         (sku,)),
        ("orders.quantity_positive", "UPDATE orders SET quantity = 0 WHERE order_id = ?", (order_id,)),
        ("orders.legal_status", "UPDATE orders SET status = 'unknown' WHERE order_id = ?", (order_id,)),
        ("orders.legal_reservation_state",
         "UPDATE orders SET status = 'cancelled', reservation_state = 'unknown' WHERE order_id = ?", (order_id,)),
        ("orders.created_state", "UPDATE orders SET status = 'created' WHERE order_id = ?", (order_id,)),
        ("orders.reserved_state", "UPDATE orders SET reservation_state = 'none' WHERE order_id = ?", (order_id,)),
        ("orders.unique_order_id",
         "INSERT INTO orders(order_id, sku, quantity, status, reservation_state) VALUES (?, ?, 1, 'created', 'none')",
         (order_id, sku)),
        ("orders.inventory_foreign_key", "UPDATE orders SET sku = ? WHERE order_id = ?", (absent, order_id)),
        ("ledger.quantity_positive",
         "UPDATE inventory_ledger SET quantity = 0, available_delta = 0, reserved_delta = 0 WHERE order_id = ?",
         (order_id,)),
        ("ledger.legal_action",
         "UPDATE inventory_ledger SET action = 'unknown' WHERE order_id = ?", (order_id,)),
        ("ledger.delta_conservation",
         "UPDATE inventory_ledger SET committed_delta = 1 WHERE order_id = ?", (order_id,)),
        ("ledger.reserve_direction",
         "UPDATE inventory_ledger SET available_delta = 1, reserved_delta = -1 WHERE order_id = ?", (order_id,)),
        ("ledger.release_direction",
         "UPDATE inventory_ledger SET action = 'release' WHERE order_id = ?", (order_id,)),
        ("ledger.unique_order_action",
         "INSERT INTO inventory_ledger(order_id, sku, action, quantity, available_delta, reserved_delta, committed_delta) "
         "VALUES (?, ?, 'reserve', 1, -1, 1, 0)", (order_id, sku)),
        ("ledger.order_foreign_key", "UPDATE inventory_ledger SET order_id = ? WHERE order_id = ?", (absent, order_id)),
        ("ledger.inventory_foreign_key", "UPDATE inventory_ledger SET sku = ? WHERE order_id = ?", (absent, order_id)),
    ]
    # Original NOT NULL guarantees are checked independently from CHECK counts.
    # SQLite TEXT PRIMARY KEY is nullable in the original schema, so the two
    # identity columns are intentionally covered by uniqueness rather than NULL.
    for column in ("initial_stock", "available", "reserved", "committed"):
        probes.append((f"inventory.{column}_not_null",
                       f"UPDATE inventory SET {column} = NULL WHERE sku = ?", (sku,)))
    for column in ("sku", "quantity", "status", "reservation_state"):
        probes.append((f"orders.{column}_not_null",
                       f"UPDATE orders SET {column} = NULL WHERE order_id = ?", (order_id,)))
    for column in ("order_id", "sku", "action", "quantity", "available_delta",
                   "reserved_delta", "committed_delta"):
        probes.append((f"ledger.{column}_not_null",
                       f"UPDATE inventory_ledger SET {column} = NULL WHERE order_id = ?", (order_id,)))

    results = []
    for name, statement, parameters in probes:
        result = {"name": name, "rejected": False, "error": None}
        with closing(sqlite3.connect(":memory:", isolation_level=None)) as copy:
            try:
                connection.backup(copy)
                copy.execute("PRAGMA trusted_schema = OFF")
                copy.execute("PRAGMA foreign_keys = ON")
                copy.execute("SAVEPOINT valid_probe_fixture")
                copy.execute(
                    "INSERT INTO inventory(sku, initial_stock, available, reserved, committed) VALUES (?, 2, 2, 0, 0)",
                    (sku,),
                )
                copy.execute(
                    "INSERT INTO orders(order_id, sku, quantity, status, reservation_state) "
                    "VALUES (?, ?, 1, 'created', 'none')", (order_id, sku),
                )
                copy.execute("UPDATE inventory SET available = 1, reserved = 1 WHERE sku = ?", (sku,))
                copy.execute("UPDATE orders SET status = 'reserved', reservation_state = 'active' WHERE order_id = ?",
                             (order_id,))
                copy.execute(
                    "INSERT INTO inventory_ledger(order_id, sku, action, quantity, available_delta, reserved_delta, "
                    "committed_delta) VALUES (?, ?, 'reserve', 1, -1, 1, 0)", (order_id, sku),
                )
                copy.execute("RELEASE valid_probe_fixture")
                copy.execute("SAVEPOINT invalid_constraint_probe")
                try:
                    copy.execute(statement, parameters)
                    # Outermost RELEASE is a commit, so deferred constraints are
                    # tested as well. Any accepted write remains in memory only.
                    copy.execute("RELEASE invalid_constraint_probe")
                except sqlite3.IntegrityError:
                    result["rejected"] = True
                finally:
                    if copy.in_transaction:
                        copy.execute("ROLLBACK")
            except sqlite3.Error as error:
                result["error"] = f"{type(error).__name__}: {error}"
        results.append(result)
    return results


def _safe_file(path: Path, data_dir: Path) -> None:
    """Reject redirection into host files before sqlite3 opens anything."""
    root = data_dir.absolute()
    path = path.absolute()
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("Data directory must not contain symbolic links")
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError("Database must be inside the trusted data directory") from error
    if ".." in relative.parts:
        raise ValueError("Database path must not contain parent traversal")
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError("Database path must not contain symbolic links")
        if parent == root:
            break
    for file in [path, Path(str(path) + "-wal"), Path(str(path) + "-shm"),
                 Path(str(path) + "-journal")]:
        if not file.exists() and not file.is_symlink():
            if file == path:
                raise ValueError("Candidate database is missing")
            continue
        info = file.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Database and sidecars must be ordinary single-link files")


def inspect_database(db_path: Path, *, expected_stock: Mapping[str, int] | None = None,
                     data_dir: Path | None = None) -> dict:
    """Return observed rows, constraint metadata and independent invariant checks.

    A malformed or unsafe database yields consistent=False with violations.
    CHECK clauses are recorded and their presence checked without requiring a
    particular SQL spelling or a particular locking/transaction repair.
    """
    path = Path(db_path)
    result = {
        "oracle_version": ORACLE_VERSION, "consistent": False, "violations": [],
        "inventory": [], "orders": [], "ledger": [], "checks": [],
        "schema": {}, "constraints": {}, "constraint_probes": [], "expected_stock": dict(expected_stock or {}),
        "db_sha256": None, "integrity_check": [], "foreign_key_check": [],
    }
    violations = result["violations"]
    try:
        _safe_file(path, Path(data_dir) if data_dir is not None else path.parent)
        result["db_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        uri = path.absolute().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5.0)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            result["integrity_check"] = [row[0] for row in connection.execute("PRAGMA integrity_check")]
            result["foreign_key_check"] = [list(row) for row in connection.execute("PRAGMA foreign_key_check")]
            if result["integrity_check"] != ["ok"]:
                violations.append("SQLite integrity_check failed")
            if result["foreign_key_check"]:
                violations.append("SQLite foreign_key_check found broken references")
            schema = {row["name"]: dict(row) for row in connection.execute(
                "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table', 'index') ORDER BY name"
            )}
            result["schema"] = schema
            for table, columns in _COLUMNS.items():
                if table not in schema or schema[table]["type"] != "table":
                    violations.append(f"Required table missing: {table}")
                    continue
                column_info = [dict(row) for row in connection.execute(f"PRAGMA table_info({table})")]
                actual = {row["name"] for row in column_info}
                if not columns <= actual:
                    violations.append(f"Required columns missing: {table}: {sorted(columns - actual)}")
                foreign_keys = [dict(row) for row in connection.execute(f"PRAGMA foreign_key_list({table})")]
                indexes = []
                for index in connection.execute(f"PRAGMA index_list({table})"):
                    detail = dict(index)
                    # Quote a schema-derived identifier; never interpolate raw SQL.
                    name = detail["name"].replace('"', '""')
                    detail["columns"] = [row["name"] for row in connection.execute(
                        f'PRAGMA index_info("{name}")'
                    )]
                    indexes.append(detail)
                sql = schema[table]["sql"] or ""
                result["constraints"][table] = {
                    "columns": column_info, "foreign_keys": foreign_keys,
                    "indexes": indexes, "check_clause_count": len(re.findall(r"\bCHECK\s*\(", sql, re.I)),
                }
                if not result["constraints"][table]["check_clause_count"]:
                    violations.append(f"No CHECK constraints remain on {table}")
            if violations:
                return result
            for table, key, order_by in [("inventory", "inventory", "sku"),
                                         ("orders", "orders", "order_id"),
                                         ("inventory_ledger", "ledger", "entry_id")]:
                result[key] = [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]
            result["constraint_probes"] = _constraint_probes(connection)
            for probe in result["constraint_probes"]:
                if probe["error"] is not None:
                    violations.append(f"Constraint probe error: {probe['name']}: {probe['error']}")
                elif probe["rejected"] is not True:
                    violations.append(f"Schema accepted invalid write: {probe['name']}")
    except (OSError, ValueError, sqlite3.Error) as error:
        violations.append(f"Database inspection error: {type(error).__name__}: {error}")
        return result

    # Inspect actual constraints, while the row oracle below remains authoritative.
    for table, primary in [("inventory", "sku"), ("orders", "order_id")]:
        unique = result["constraints"][table]["indexes"]
        if not any(index["unique"] and index["columns"] == [primary] for index in unique):
            violations.append(f"Missing unique identity constraint: {table}.{primary}")
    unique = result["constraints"]["inventory_ledger"]["indexes"]
    if not any(index["unique"] and set(index["columns"]) == {"order_id", "action"} for index in unique):
        violations.append("Missing unique ledger constraint: (order_id, action)")
    for table, source, target, destination in [
        ("orders", "sku", "inventory", "sku"),
        ("inventory_ledger", "order_id", "orders", "order_id"),
        ("inventory_ledger", "sku", "inventory", "sku"),
    ]:
        if not any(fk["from"] == source and fk["table"] == target and fk["to"] == destination
                   for fk in result["constraints"][table]["foreign_keys"]):
            violations.append(f"Missing foreign key: {table}.{source} -> {target}.{destination}")

    inventory = {row["sku"]: row for row in result["inventory"]}
    orders = {row["order_id"]: row for row in result["orders"]}
    if len(inventory) != len(result["inventory"]) or len(orders) != len(result["orders"]):
        violations.append("Duplicate inventory or order identities")
    if expected_stock is not None:
        if set(inventory) != set(expected_stock):
            violations.append("Inventory SKU set differs from trusted fixture")
        for sku, initial in expected_stock.items():
            if sku in inventory and inventory[sku]["initial_stock"] != initial:
                violations.append(f"Initial stock differs from trusted fixture: {sku}")
    action_counts = Counter((entry["order_id"], entry["action"]) for entry in result["ledger"])
    if any(count != 1 for count in action_counts.values()):
        violations.append("Duplicate ledger action for one order")
    for entry in result["ledger"]:
        order = orders.get(entry["order_id"])
        quantity = entry["quantity"]
        if order is None or entry["sku"] not in inventory:
            violations.append(f"Orphan ledger entry: {entry['entry_id']}")
        elif entry["sku"] != order["sku"] or quantity != order["quantity"]:
            violations.append(f"Ledger differs from its order: {entry['entry_id']}")
        direction = {"reserve": -1, "release": 1}.get(entry["action"])
        if (type(quantity) is not int or quantity <= 0 or direction is None
                or entry["available_delta"] != direction * quantity
                or entry["reserved_delta"] != -direction * quantity
                or entry["committed_delta"] != 0):
            violations.append(f"Invalid ledger quantity/action/deltas: {entry['entry_id']}")
    for order in result["orders"]:
        legal = ((order["status"], order["reservation_state"]) in {
            ("created", "none"), ("reserved", "active"),
            ("cancelled", "none"), ("cancelled", "released"),
        })
        if not legal or type(order["quantity"]) is not int or order["quantity"] <= 0:
            violations.append(f"Invalid order state/quantity: {order['order_id']}")
        if order["sku"] not in inventory:
            violations.append(f"Order refers to missing inventory: {order['order_id']}")
        expected = {"none": Counter(), "active": Counter({"reserve": 1}),
                    "released": Counter({"reserve": 1, "release": 1})}.get(order["reservation_state"])
        actual = Counter(entry["action"] for entry in result["ledger"] if entry["order_id"] == order["order_id"])
        if actual != expected:
            violations.append(f"Order reservation differs from ledger: {order['order_id']}")
    for sku, row in inventory.items():
        values = [row[key] for key in ("initial_stock", "available", "reserved", "committed")]
        if any(type(value) is not int for value in values):
            violations.append(f"Non-integer inventory: {sku}")
            continue
        entries = [entry for entry in result["ledger"] if entry["sku"] == sku]
        sku_orders = [order for order in result["orders"] if order["sku"] == sku]
        try:
            check = {
                "sku": sku, "nonnegative": all(value >= 0 for value in values),
                "conservation": row["available"] + row["reserved"] + row["committed"] == row["initial_stock"],
                "ledger_matches": (
                    row["available"] == row["initial_stock"] + sum(entry["available_delta"] for entry in entries)
                    and row["reserved"] == sum(entry["reserved_delta"] for entry in entries)
                    and row["committed"] == sum(entry["committed_delta"] for entry in entries)
                ),
                "order_reservations_match": row["reserved"] == sum(
                    order["quantity"] for order in sku_orders if order["reservation_state"] == "active"
                ),
            }
        except TypeError:
            violations.append(f"Malformed numeric accounting data: {sku}")
            continue
        result["checks"].append(check)
        for key, value in check.items():
            if key != "sku" and value is not True:
                violations.append(f"{sku}: {key} failed")
    result["consistent"] = not violations
    return result
