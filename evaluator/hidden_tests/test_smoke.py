"""Private SMOKE-001 truth: assertions execute only in the evaluator host."""

import pytest
import json

from evaluator.oracle import inspect_database

from evaluator.rpc import RemoteBusinessError


def assert_stock(client, available, reserved=0, sku="SKU-1"):
    stock = client.call("get_inventory", sku=sku)
    assert stock["available"] == available
    assert stock["reserved"] == reserved
    assert stock["committed"] == 0
    assert stock["available"] + stock["reserved"] == stock["initial_stock"]


def assert_consistent(client, expected_stock=None):
    audit = client.call("audit")
    assert audit["consistent"] is True
    assert all(
        all(value is True for key, value in check.items() if key != "sku")
        for check in audit["checks"]
    )
    # Retain the API regression assertions and independently inspect persisted truth.
    client.close()
    oracle = inspect_database(client.data_dir / "business.sqlite", data_dir=client.data_dir,
                              expected_stock=expected_stock or {"SKU-1": 10, "SKU-2": 4})
    path = client.log_path.parent / f"oracle-{client.log_path.stem}-{client._next_id}.json"
    path.write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n")
    assert oracle["consistent"] is True, oracle["violations"]
    client.start()
    return oracle


def test_cancel_restores_stock_exactly_once(client):
    assert_stock(client, 10)
    assert client.call("create_order", order_id="smoke", sku="SKU-1", quantity=3)["status"] == "reserved"
    assert_stock(client, 7, 3)
    assert client.call("cancel_order", order_id="smoke")["status"] == "cancelled"
    assert_stock(client, 10)
    for _ in range(4):
        assert client.call("cancel_order", order_id="smoke")["reservation_state"] == "released"
        assert_stock(client, 10)
    client.call("release_inventory", order_id="smoke")
    assert_stock(client, 10)
    audit = assert_consistent(client)
    assert [entry["action"] for entry in audit["ledger"]] == ["reserve", "release"]


def test_multiple_orders_preserve_accounting(client):
    client.call("create_order", order_id="first", sku="SKU-1", quantity=3)
    client.call("create_order", order_id="second", sku="SKU-1", quantity=5)
    assert_stock(client, 2, 8)
    client.call("cancel_order", order_id="first")
    assert_stock(client, 5, 5)
    client.call("cancel_order", order_id="first")
    assert_stock(client, 5, 5)
    client.call("cancel_order", order_id="second")
    assert_stock(client, 10)
    audit = assert_consistent(client)
    assert len(audit["orders"]) == 2
    assert len(audit["ledger"]) == 4


def test_cancel_without_reservation_does_not_create_stock(client):
    client.call("create_order", order_id="unreserved", sku="SKU-1", quantity=3, reserve=False)
    for _ in range(3):
        client.call("cancel_order", order_id="unreserved")
        assert_stock(client, 10)
    with pytest.raises(RemoteBusinessError, match="InvalidOrderState"):
        client.call("reserve_inventory", order_id="unreserved")
    assert assert_consistent(client)["ledger"] == []


def test_creation_and_reservation_are_idempotent(client):
    client.call("create_order", order_id="duplicate", sku="SKU-1", quantity=3, reserve=False)
    assert_stock(client, 10)
    client.call("reserve_inventory", order_id="duplicate")
    client.call("reserve_inventory", order_id="duplicate")
    client.call("create_order", order_id="duplicate", sku="SKU-1", quantity=3)
    assert_stock(client, 7, 3)
    with pytest.raises(RemoteBusinessError, match="OrderConflict"):
        client.call("create_order", order_id="duplicate", sku="SKU-1", quantity=4)
    with pytest.raises(RemoteBusinessError, match="InvalidOrderState"):
        client.call("release_inventory", order_id="duplicate")
    assert_stock(client, 7, 3)
    assert len(assert_consistent(client)["ledger"]) == 1


def test_insufficient_inventory_rolls_back_creation(client):
    with pytest.raises(RemoteBusinessError, match="InsufficientInventory"):
        client.call("create_order", order_id="too-large", sku="SKU-1", quantity=11)
    with pytest.raises(RemoteBusinessError, match="OrderNotFound"):
        client.call("get_order", order_id="too-large")
    assert_stock(client, 10)
    audit = assert_consistent(client)
    assert audit["orders"] == []
    assert audit["ledger"] == []
    client.call("create_order", order_id="valid", sku="SKU-1", quantity=10)
    assert_stock(client, 0, 10)


def test_database_initialization_and_reset(client):
    client.call("create_order", order_id="old", sku="SKU-1", quantity=3)
    client.call("initialize", stock={"SKU-1": 10, "SKU-2": 4})
    assert_stock(client, 7, 3)
    with pytest.raises(RemoteBusinessError, match="FixtureConflict"):
        client.call("initialize", stock={"SKU-1": 9})
    assert_stock(client, 7, 3)
    client.call("initialize", stock={"SKU-1": 10}, reset=True)
    assert_stock(client, 10)
    with pytest.raises(RemoteBusinessError, match="OrderNotFound"):
        client.call("get_order", order_id="old")
    with pytest.raises(RemoteBusinessError, match="InventoryNotFound"):
        client.call("get_inventory", sku="SKU-2")
    assert assert_consistent(client, {"SKU-1": 10})["ledger"] == []
    client.call("initialize", stock={"SKU-1": 10}, reset=True)
    assert_stock(client, 10)


def test_state_survives_worker_restart(client):
    client.call("create_order", order_id="persistent", sku="SKU-1", quantity=3)
    client.restart()
    assert_stock(client, 7, 3)
    assert client.call("get_order", order_id="persistent")["status"] == "reserved"
    client.call("cancel_order", order_id="persistent")
    client.restart()
    assert_stock(client, 10)
    client.call("cancel_order", order_id="persistent")
    assert_stock(client, 10)
    assert len(assert_consistent(client)["ledger"]) == 2


def test_invalid_requests_leave_inventory_unchanged(client):
    for quantity in [0, -1, True, 1.5, "3"]:
        with pytest.raises(RemoteBusinessError, match="InvalidInput"):
            client.call("create_order", order_id="invalid", sku="SKU-1", quantity=quantity)
    with pytest.raises(RemoteBusinessError, match="InventoryNotFound"):
        client.call("create_order", order_id="missing-stock", sku="missing", quantity=1)
    with pytest.raises(RemoteBusinessError, match="OrderNotFound"):
        client.call("cancel_order", order_id="missing-order")
    assert_stock(client, 10)
    audit = assert_consistent(client)
    assert audit["orders"] == []
    assert audit["ledger"] == []
