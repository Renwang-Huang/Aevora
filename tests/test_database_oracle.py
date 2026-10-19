"""Independent oracle checks use actual SQLite files, never candidate audit()."""

import hashlib
import os
import sqlite3

import pytest

from app.service import OrderFlow
from evaluator.oracle import inspect_database


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "business.sqlite"
    flow = OrderFlow(path)
    flow.initialize({"SKU-1": 10})
    return path, flow


def inspect(path, expected_stock=None, **kwargs):
    return inspect_database(path, expected_stock={"SKU-1": 10} if expected_stock is None else expected_stock,
                            **kwargs)


def test_pristine_database_is_consistent_and_read_only(database):
    path, _ = database
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = inspect(path)
    assert result["consistent"] is True
    assert result["integrity_check"] == ["ok"]
    assert result["foreign_key_check"] == []
    assert result["db_sha256"] == before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert result["orders"] == result["ledger"] == []
    assert result["constraints"]["inventory"]["check_clause_count"] >= 1
    assert result["constraints"]["orders"]["foreign_keys"]
    assert any(index["unique"] for index in result["constraints"]["inventory_ledger"]["indexes"])
    assert result["constraint_probes"]
    assert all(probe["rejected"] and probe["error"] is None for probe in result["constraint_probes"])


def test_reserved_and_cancelled_order_accounting(database):
    path, flow = database
    flow.create_order("active", "SKU-1", 2)
    flow.create_order("cancelled", "SKU-1", 3)
    flow.cancel_order("cancelled")
    flow.cancel_order("cancelled")
    flow.create_order("unreserved", "SKU-1", 1, reserve=False)
    result = inspect(path)
    assert result["consistent"] is True
    assert result["inventory"][0]["reserved"] == 2
    assert len(result["orders"]) == 3
    assert len(result["ledger"]) == 3


def test_candidate_audit_cannot_hide_a_lost_update(database, monkeypatch):
    path, flow = database
    flow.create_order("purchase", "SKU-1", 3)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE inventory SET available = 8, reserved = 2")
    monkeypatch.setattr(OrderFlow, "audit", lambda self: {"consistent": True, "checks": []})
    assert flow.audit()["consistent"] is True
    result = inspect(path)
    assert result["consistent"] is False
    assert "SKU-1: ledger_matches failed" in result["violations"]
    assert "SKU-1: order_reservations_match failed" in result["violations"]


def test_expected_fixture_is_host_authority(database):
    path, _ = database
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE inventory SET initial_stock = 50, available = 50")
    result = inspect(path)
    assert result["consistent"] is False
    assert "Initial stock differs from trusted fixture: SKU-1" in result["violations"]


def test_order_ledger_action_and_quantity_checked(database):
    path, flow = database
    flow.create_order("purchase", "SKU-1", 3)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("UPDATE inventory_ledger SET quantity = 4")
    result = inspect(path)
    assert result["consistent"] is False
    # integrity_check also diagnoses bypassed CHECKs; either independent route
    # rejects this actual malformed ledger rather than accepting audit output.
    assert result["violations"]


def test_cancelled_state_requires_a_matching_release_entry(database):
    path, flow = database
    flow.create_order("purchase", "SKU-1", 3)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE orders SET status = 'cancelled', reservation_state = 'released'")
    result = inspect(path)
    assert result["consistent"] is False
    assert "Order reservation differs from ledger: purchase" in result["violations"]


def test_foreign_key_violations_detected_independently(database):
    path, _ = database
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("INSERT INTO orders VALUES ('orphan', 'absent', 1, 'created', 'none')")
    result = inspect(path)
    assert result["consistent"] is False
    assert result["foreign_key_check"]


@pytest.mark.parametrize("link_type", ["symbolic", "hard"])
def test_external_links_are_rejected_before_database_open(database, tmp_path, link_type):
    path, _ = database
    link = tmp_path / "redirected.sqlite"
    if link_type == "symbolic":
        link.symlink_to(path)
    else:
        os.link(path, link)
    result = inspect(link, data_dir=tmp_path)
    assert result["consistent"] is False
    assert result["db_sha256"] is None
    assert result["inventory"] == []


def test_database_outside_trusted_data_directory_is_rejected(database, tmp_path):
    path, _ = database
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    result = inspect(path, data_dir=allowed)
    assert result["consistent"] is False
    assert "inside the trusted data directory" in result["violations"][0]


def test_linked_sidecar_is_rejected(database, tmp_path):
    path, _ = database
    unrelated = tmp_path / "host-file"
    unrelated.write_bytes(b"private host bytes")
    (tmp_path / "business.sqlite-wal").symlink_to(unrelated)
    result = inspect(path)
    assert result["consistent"] is False
    assert result["db_sha256"] is None
    assert unrelated.read_bytes() == b"private host bytes"


def test_missing_database_and_schema_fail_closed(tmp_path):
    path = tmp_path / "missing.sqlite"
    assert inspect(path)["consistent"] is False
    assert not path.exists()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value INTEGER)")
    result = inspect(path)
    assert result["consistent"] is False
    assert "Required table missing: inventory" in result["violations"]


def test_removed_check_constraints_are_recorded_and_rejected(database):
    path, _ = database
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = ? WHERE name = 'inventory'",
            ("CREATE TABLE inventory (sku TEXT PRIMARY KEY, initial_stock INTEGER NOT NULL, "
             "available INTEGER NOT NULL, reserved INTEGER NOT NULL DEFAULT 0, "
             "committed INTEGER NOT NULL DEFAULT 0)",),
        )
    result = inspect(path)
    assert result["consistent"] is False
    assert result["constraints"]["inventory"]["check_clause_count"] == 0
    assert "No CHECK constraints remain on inventory" in result["violations"]


@pytest.mark.parametrize("table,original,replacement,probe_name", [
    ("inventory", "CHECK (available >= 0)", "", "inventory.available_nonnegative"),
    ("inventory", "CHECK (reserved >= 0)", "CHECK (1)", "inventory.reserved_nonnegative"),
    ("inventory", "CHECK (available + reserved + committed = initial_stock)", "CHECK (1)",
     "inventory.stock_conservation"),
    ("orders", "CHECK (quantity > 0)", "CHECK (1)", "orders.quantity_positive"),
    ("orders", "CHECK (status != 'created' OR reservation_state = 'none')", "CHECK (1)",
     "orders.created_state"),
    ("orders", "quantity INTEGER NOT NULL", "quantity INTEGER", "orders.quantity_not_null"),
    ("inventory_ledger", "CHECK (quantity > 0)", "CHECK (1)", "ledger.quantity_positive"),
])
def test_one_removed_or_vacuous_check_cannot_pass(database, table, original, replacement, probe_name):
    path, _ = database
    with sqlite3.connect(path) as connection:
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
        assert schema.count(original) == 1
        altered = schema.replace(original, replacement, 1)
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("UPDATE sqlite_master SET sql = ? WHERE name = ?", (altered, table))
    before = path.read_bytes()
    result = inspect(path)
    assert result["consistent"] is False
    assert result["constraints"][table]["check_clause_count"] > 0
    probe = next(probe for probe in result["constraint_probes"] if probe["name"] == probe_name)
    assert probe["rejected"] is False
    assert probe["error"] is None
    assert f"Schema accepted invalid write: {probe_name}" in result["violations"]
    assert path.read_bytes() == before


def test_constraint_probes_preserve_actual_database_rows_and_schema(database):
    path, flow = database
    flow.create_order("keep-active", "SKU-1", 3)
    before_bytes = path.read_bytes()
    before_audit = flow.audit()
    result = inspect(path)
    assert result["consistent"] is True, result["violations"]
    assert all(probe["rejected"] and probe["error"] is None for probe in result["constraint_probes"])
    assert path.read_bytes() == before_bytes
    assert flow.audit() == before_audit


def test_equivalent_check_spelling_is_accepted(database):
    path, _ = database
    with sqlite3.connect(path) as connection:
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'inventory'").fetchone()[0]
        altered = schema.replace("CHECK (available >= 0)", "CHECK (NOT (available < 0))")
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("UPDATE sqlite_master SET sql = ? WHERE name = 'inventory'", (altered,))
    result = inspect(path)
    assert result["consistent"] is True, result["violations"]


def test_deferred_foreign_keys_are_verified_at_probe_commit(database):
    path, _ = database
    with sqlite3.connect(path) as connection:
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'orders'").fetchone()[0]
        altered = schema.replace("REFERENCES inventory(sku)",
                                 "REFERENCES inventory(sku) DEFERRABLE INITIALLY DEFERRED")
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("UPDATE sqlite_master SET sql = ? WHERE name = 'orders'", (altered,))
    before = path.read_bytes()
    result = inspect(path)
    assert result["consistent"] is True, result["violations"]
    probe = next(probe for probe in result["constraint_probes"] if probe["name"] == "orders.inventory_foreign_key")
    assert probe["rejected"] is True
    assert probe["error"] is None
    assert path.read_bytes() == before
