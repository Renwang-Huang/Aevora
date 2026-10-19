"""Evaluate the same real recovery defect through different legal SQLite APIs."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.episodes.episode_d import build_episode_d_fixture
from benchmark.submission import snapshot_source_tree, source_tree_sha256
from scripts.reproduce_episode_d import run_record


COMPENSATED_PHASE_SOURCE = '''

# A recoverable preliminary creation precedes the final reservation.
from collections.abc import Mapping
import fcntl
import functools
import threading

from app.errors import InsufficientInventory
from app.persistence import validate_identifier, validate_quantity

_phase_initialize_original = OrderFlow.initialize
_phase_process_lock = threading.RLock()

def _phase_marker_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS provisional_orders (
        order_id TEXT PRIMARY KEY NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE
    )""")

def _phase_initialize(self, stock, reset=False):
    # Validate before changing the auxiliary recovery metadata, just as the
    # ordinary initializer validates before resetting the original tables.
    if not isinstance(stock, Mapping):
        raise InvalidInput("stock must map SKU strings to nonnegative integers")
    for sku, quantity in stock.items():
        validate_identifier(sku, "sku")
        validate_quantity(quantity, allow_zero=True)
    if reset:
        with self.persistence.transaction() as connection:
            connection.execute("DROP TABLE IF EXISTS provisional_orders")
    _phase_initialize_original(self, stock, reset=reset)
    with self.persistence.transaction() as connection:
        _phase_marker_schema(connection)

def _phase_create_order(self, order_id, sku, quantity, *, reserve=True):
    if type(reserve) is not bool:
        raise InvalidInput("reserve must be a boolean")
    validate_identifier(order_id, "order_id")
    validate_identifier(sku, "sku")
    validate_quantity(quantity)

    # The order and its provisional provenance are committed together. A
    # surviving created/none order has no inventory effect or reserve ledger.
    with self.persistence.transaction() as connection:
        _phase_marker_schema(connection)
        existed = connection.execute("SELECT 1 FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        order = self.orders.create(connection, order_id, sku, quantity)
        if reserve and existed is None:
            connection.execute("INSERT INTO provisional_orders(order_id) VALUES (?)", (order_id,))

    if not reserve or order["status"] != "created":
        return order
    try:
        # Conditional stock update, the order transition, the immutable
        # reserve entry and marker removal form one atomic final transaction.
        with self.persistence.transaction() as connection:
            order = self.inventory.reserve(connection, order_id)
            connection.execute("DELETE FROM provisional_orders WHERE order_id = ?", (order_id,))
            return order
    except InsufficientInventory:
        # The reservation transaction already rolled back. Delete only an
        # unfinished order whose durable marker proves provisional creation.
        # The enclosing cross-process guard excludes another writer between
        # this failure and compensation; intentionally created orders remain.
        with self.persistence.transaction() as connection:
            row = connection.execute(
                "SELECT orders.status, orders.reservation_state FROM orders "
                "JOIN provisional_orders USING(order_id) WHERE order_id = ?", (order_id,),
            ).fetchone()
            if row is not None and row["status"] == "created" and row["reservation_state"] == "none":
                connection.execute("DELETE FROM provisional_orders WHERE order_id = ?", (order_id,))
                connection.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        raise

def _phase_reserve_inventory(self, order_id):
    with self.persistence.transaction() as connection:
        result = self.inventory.reserve(connection, order_id)
        connection.execute("DELETE FROM provisional_orders WHERE order_id = ?", (order_id,))
        return result

def _phase_cancel_order(self, order_id):
    with self.persistence.transaction() as connection:
        self.orders.mark_cancelled(connection, order_id)
        result = self.inventory.release(connection, order_id)
        connection.execute("DELETE FROM provisional_orders WHERE order_id = ?", (order_id,))
        return result

def _phase_release_inventory(self, order_id):
    with self.persistence.transaction() as connection:
        result = self.inventory.release(connection, order_id)
        connection.execute("DELETE FROM provisional_orders WHERE order_id = ?", (order_id,))
        return result

def _phase_coordinate(method):
    @functools.wraps(method)
    def guarded(self, *args, **kwargs):
        with _phase_process_lock:
            self.persistence.db_path.parent.mkdir(parents=True, exist_ok=True)
            # Stable per-database file, freshly opened for each operation.
            # Kernel flock is released automatically on abnormal process exit.
            with open(str(self.persistence.db_path) + ".phase-write.lock", "a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    return method(self, *args, **kwargs)
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return guarded

for _name, _method in {
        "initialize": _phase_initialize,
        "create_order": _phase_create_order,
        "reserve_inventory": _phase_reserve_inventory,
        "cancel_order": _phase_cancel_order,
        "release_inventory": _phase_release_inventory}.items():
    setattr(OrderFlow, _name, _phase_coordinate(_method))
'''


def direct_transaction(workspace, style):
    source = workspace / "app/service.py"
    if style == "compensated-phase":
        source.write_text(source.read_text()+COMPENSATED_PHASE_SOURCE)
        return
    if style == "two-phase":
        source.write_text(source.read_text()+'''\n_original_create = OrderFlow.create_order
def _recoverable_phased_create(self, order_id, sku, quantity, reserve=True):
    result = _original_create(self, order_id, sku, quantity, reserve=False)
    if reserve and result["status"] == "created":
        return self.reserve_inventory(order_id)
    return result
OrderFlow.create_order = _recoverable_phased_create
''')
        return
    body = {
        "commit": "connection.commit()",
        "sql": "connection.execute('COMMIT')",
        "cursor": "connection.cursor().execute('END TRANSACTION')",
        "read-first": "connection.commit()",
        "cache-first": "connection.commit()",
        "metrics-first": "connection.commit()",
    }
    if style == "context":
        helper = '''\nfrom contextlib import contextmanager
@contextmanager
def _direct_transaction(persistence):
    with persistence.connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        with connection:
            yield connection
'''
    else:
        helper = '''\nfrom contextlib import contextmanager
@contextmanager
def _direct_transaction(persistence):
    with persistence.connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            COMMIT
        except BaseException:
            connection.rollback()
            raise
'''.replace("COMMIT", body[style])
    if style == "read-first":
        helper = helper.replace('        connection.execute("BEGIN IMMEDIATE")',
            '        connection.execute("BEGIN")\n        connection.execute("SELECT 1").fetchall()\n'
            '        connection.commit()\n        connection.execute("BEGIN IMMEDIATE")')
    if style == "cache-first":
        helper = helper.replace('    with persistence.connection() as connection:',
            '    import sqlite3\n    with sqlite3.connect(str(persistence.db_path)+".cache", timeout=30) as cache:\n'
            '        cache.execute("CREATE TABLE IF NOT EXISTS cache_ticks (value INTEGER)")\n'
            '        cache.execute("INSERT INTO cache_ticks VALUES (1)")\n'
            '    with persistence.connection() as connection:')
    if style == "metrics-first":
        helper = helper.replace('        connection.execute("BEGIN IMMEDIATE")',
            '        connection.execute("BEGIN IMMEDIATE")\n'
            '        connection.execute("CREATE TABLE IF NOT EXISTS diagnostic_ticks (value INTEGER)")\n'
            '        connection.execute("INSERT INTO diagnostic_ticks VALUES (1)")\n'
            '        connection.commit()\n        connection.execute("BEGIN IMMEDIATE")')
    source.write_text(source.read_text().replace("with self.persistence.transaction() as connection:",
        "with _direct_transaction(self.persistence) as connection:") + helper)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--preserved-counterexample", type=Path, required=True)
    parser.add_argument("--styles", nargs="+", choices=["commit", "sql", "cursor", "context", "read-first", "cache-first", "metrics-first", "two-phase", "compensated-phase"])
    args = parser.parse_args()
    archive = args.archive.resolve()
    archive.mkdir(parents=True, exist_ok=False)
    records = []
    for style in (args.styles or ("commit", "sql", "cursor", "context", "read-first", "cache-first", "metrics-first", "two-phase", "compensated-phase")):
        for strategy in (("reference",) if style in {"read-first", "cache-first", "metrics-first", "two-phase", "compensated-phase"}
                         else ("reference", "split-ledger")):
            workspace = build_episode_d_fixture(archive / f"{style}-{strategy}", strategy=strategy)
            direct_transaction(workspace, style)
            candidate = snapshot_source_tree(workspace)
            repetitions = 3 if (style, strategy) == ("commit", "split-ledger") else 1
            if repetitions == 3:
                original = snapshot_source_tree(args.preserved_counterexample.resolve())
                assert candidate == original, "Counterexample candidate bytes must be unchanged"
            for trial in range(1, repetitions + 1):
                receipt, report = run_record(archive / f"command-{style}-{strategy}-{trial}", [
                    sys.executable, "-m", "benchmark.cli", "--runs-root", str(archive / "runs"),
                    "evaluate", "--episode", "D", "--submission", str(workspace)])
                expected = "PASS" if strategy == "reference" and style != "two-phase" else "FAIL"
                tests = report.get("test_results") or {}
                coverage = report.get("recovery_coverage", {})
                valid = (receipt["status"] == expected and receipt["exit_code"] == (0 if expected == "PASS" else 1)
                         and tests.get("errors") == 0 and tests.get("skipped") == 0
                         and coverage.get("points", {}).get("transaction_committed", {}).get("availability") == "AVAILABLE")
                if expected == "FAIL" and style != "two-phase":
                    valid = valid and any(not row.get("consistent", False) for row in report.get("database_oracle", []))
                records.append({"style": style, "strategy": strategy, "trial": trial, "checks_pass": valid,
                                "candidate_sha256": source_tree_sha256(candidate), "command": receipt,
                                "control_semantics": "Known-bad: insufficient reserve leaves newly created order" if style == "two-phase" else "SQLite boundary / compensated phase control",
                                "recovery_coverage": coverage})
                (archive / "summary.json").write_text(json.dumps({"result": "PASS" if all(r["checks_pass"] for r in records)
                            else "FAIL", "records": records}, indent=2) + "\n")
                print(json.dumps({"style": style, "strategy": strategy, "trial": trial, "run_id": receipt["run_id"],
                                  "status": receipt["status"], "checks_pass": valid}), flush=True)
    return 0 if all(r["checks_pass"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
