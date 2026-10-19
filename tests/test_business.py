"""Public regression coverage for the minimal business environment."""

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest

from app.errors import (FixtureConflict, InsufficientInventory, InvalidInput,
                        InvalidOrderState, InventoryNotFound, OrderConflict, OrderNotFound)
from app.service import OrderFlow


@pytest.fixture
def flow(tmp_path):
    service = OrderFlow(tmp_path / "business.sqlite")
    service.initialize({"SKU-1": 10, "SKU-2": 4})
    return service


def test_cancel_restores_inventory_exactly_once(flow):
    order = flow.create_order("order-1", "SKU-1", 3)
    assert order["status"] == "reserved"
    assert flow.get_inventory("SKU-1")["available"] == 7
    assert flow.get_inventory("SKU-1")["reserved"] == 3
    assert flow.cancel_order("order-1")["status"] == "cancelled"
    assert flow.get_inventory("SKU-1")["available"] == 10
    for _ in range(5):
        assert flow.cancel_order("order-1")["reservation_state"] == "released"
        assert flow.release_inventory("order-1")["status"] == "cancelled"
    assert flow.get_inventory("SKU-1")["available"] == 10
    assert flow.get_inventory("SKU-1")["reserved"] == 0
    audit = flow.audit()
    assert audit["consistent"]
    assert [entry["action"] for entry in audit["ledger"]] == ["reserve", "release"]
    json.dumps(audit)


def test_separate_creation_and_reservation_are_idempotent(flow):
    assert flow.create_order("order-1", "SKU-1", 3, reserve=False)["status"] == "created"
    assert flow.get_inventory("SKU-1")["available"] == 10
    assert flow.reserve_inventory("order-1")["status"] == "reserved"
    flow.reserve_inventory("order-1")
    flow.create_order("order-1", "SKU-1", 3)
    assert flow.get_inventory("SKU-1")["available"] == 7
    assert len(flow.audit()["ledger"]) == 1
    with pytest.raises(InvalidOrderState):
        flow.release_inventory("order-1")


def test_cancelling_unreserved_order_does_not_add_stock(flow):
    flow.create_order("order-1", "SKU-1", 3, reserve=False)
    flow.cancel_order("order-1")
    flow.cancel_order("order-1")
    assert flow.get_inventory("SKU-1")["available"] == 10
    assert flow.audit()["ledger"] == []
    with pytest.raises(InvalidOrderState):
        flow.reserve_inventory("order-1")


def test_insufficient_stock_rolls_back_order_and_inventory(flow):
    with pytest.raises(InsufficientInventory):
        flow.create_order("too-large", "SKU-1", 11)
    with pytest.raises(OrderNotFound):
        flow.get_order("too-large")
    assert flow.get_inventory("SKU-1")["available"] == 10
    assert flow.audit()["ledger"] == []
    assert flow.audit()["consistent"]


def test_duplicate_order_with_different_contents_is_rejected(flow):
    flow.create_order("order-1", "SKU-1", 3)
    with pytest.raises(OrderConflict):
        flow.create_order("order-1", "SKU-1", 4)
    with pytest.raises(OrderConflict):
        flow.create_order("order-1", "SKU-2", 3)
    assert flow.get_inventory("SKU-1")["available"] == 7
    assert flow.get_inventory("SKU-2")["available"] == 4


def test_initialize_is_idempotent_and_reset_removes_state(flow):
    flow.create_order("order-1", "SKU-1", 3)
    flow.initialize({"SKU-1": 10, "SKU-2": 4})
    assert flow.get_inventory("SKU-1")["available"] == 7
    with pytest.raises(FixtureConflict):
        flow.initialize({"SKU-1": 9})
    assert flow.get_inventory("SKU-1")["available"] == 7
    flow.initialize({"SKU-1": 10}, reset=True)
    assert flow.get_inventory("SKU-1")["available"] == 10
    with pytest.raises(OrderNotFound):
        flow.get_order("order-1")
    with pytest.raises(InventoryNotFound):
        flow.get_inventory("SKU-2")
    assert flow.audit()["ledger"] == []
    flow.initialize({"SKU-1": 10}, reset=True)
    assert flow.audit()["consistent"]


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5, "3"])
def test_invalid_order_quantities_are_rejected(flow, quantity):
    with pytest.raises(InvalidInput):
        flow.create_order("invalid", "SKU-1", quantity)
    assert flow.audit()["orders"] == []


def test_missing_inventory_and_order_are_business_errors(flow):
    with pytest.raises(InventoryNotFound):
        flow.create_order("order-1", "missing", 1)
    with pytest.raises(OrderNotFound):
        flow.cancel_order("missing")
    assert flow.audit()["consistent"]


def test_failure_between_inventory_update_and_ledger_is_atomic(flow, monkeypatch):
    original_record = flow.inventory._record

    def fail_record(*args, **kwargs):
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(flow.inventory, "_record", fail_record)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        flow.create_order("order-1", "SKU-1", 3)
    assert flow.get_inventory("SKU-1")["available"] == 10
    assert flow.audit()["orders"] == []
    monkeypatch.setattr(flow.inventory, "_record", original_record)
    flow.create_order("order-1", "SKU-1", 3)
    monkeypatch.setattr(flow.inventory, "_record", fail_record)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        flow.cancel_order("order-1")
    assert flow.get_order("order-1")["status"] == "reserved"
    assert flow.get_inventory("SKU-1")["available"] == 7
    assert flow.audit()["consistent"]


def test_database_constraints_and_audit_reject_accounting_corruption(flow):
    with sqlite3.connect(flow.persistence.db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE inventory SET available = -1 WHERE sku = 'SKU-1'")
        connection.execute("UPDATE inventory SET available = 9, reserved = 1 WHERE sku = 'SKU-1'")
    audit = flow.audit()
    assert not audit["consistent"]
    assert not audit["checks"][0]["ledger_matches"]
    assert not audit["checks"][0]["order_reservations_match"]


def test_connections_share_persistent_state_without_overselling(flow):
    def reserve_one(index):
        client = OrderFlow(flow.persistence.db_path)
        try:
            client.create_order(f"order-{index}", "SKU-1", 1)
            return True
        except InsufficientInventory:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(reserve_one, range(16)))
    assert sum(outcomes) == 10
    assert flow.get_inventory("SKU-1")["available"] == 0
    assert flow.get_inventory("SKU-1")["reserved"] == 10
    assert len(flow.audit()["orders"]) == 10
    assert flow.audit()["consistent"]
