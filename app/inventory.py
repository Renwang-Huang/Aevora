"""Inventory changes and their immutable per-order accounting entries."""

import sqlite3

from app.errors import InsufficientInventory, InventoryNotFound, InvalidOrderState
from app.orders import OrderService
from app.persistence import validate_identifier


class InventoryService:
    def __init__(self, orders: OrderService):
        self.orders = orders

    def get(self, connection: sqlite3.Connection, sku: str) -> dict:
        validate_identifier(sku, "sku")
        row = connection.execute("SELECT * FROM inventory WHERE sku = ?", (sku,)).fetchone()
        if row is None:
            raise InventoryNotFound(sku)
        return dict(row)

    def reserve(self, connection: sqlite3.Connection, order_id: str) -> dict:
        order = self.orders.get(connection, order_id)
        if order["status"] == "cancelled":
            raise InvalidOrderState("A cancelled order cannot reserve inventory")
        if order["reservation_state"] == "active":
            return order
        cursor = connection.execute(
            "UPDATE inventory SET available = available - ?, reserved = reserved + ? "
            "WHERE sku = ? AND available >= ?",
            (order["quantity"], order["quantity"], order["sku"], order["quantity"]),
        )
        if cursor.rowcount != 1:
            raise InsufficientInventory(order["sku"])
        connection.execute(
            "UPDATE orders SET status = 'reserved', reservation_state = 'active' WHERE order_id = ?",
            (order_id,),
        )
        self._record(connection, order, "reserve", -order["quantity"], order["quantity"])
        return self.orders.get(connection, order_id)

    def release(self, connection: sqlite3.Connection, order_id: str) -> dict:
        order = self.orders.get(connection, order_id)
        if order["status"] != "cancelled":
            raise InvalidOrderState("Inventory release requires a cancelled order")
        if order["reservation_state"] != "active":
            return order
        connection.execute(
            "UPDATE inventory SET available = available + ?, reserved = reserved - ? WHERE sku = ?",
            (order["quantity"], order["quantity"], order["sku"]),
        )
        connection.execute(
            "UPDATE orders SET reservation_state = 'released' WHERE order_id = ?", (order_id,)
        )
        self._record(connection, order, "release", order["quantity"], -order["quantity"])
        return self.orders.get(connection, order_id)

    @staticmethod
    def _record(connection: sqlite3.Connection, order: dict, action: str,
                available_delta: int, reserved_delta: int) -> None:
        connection.execute(
            "INSERT INTO inventory_ledger(order_id, sku, action, quantity, "
            "available_delta, reserved_delta) VALUES (?, ?, ?, ?, ?, ?)",
            (order["order_id"], order["sku"], action, order["quantity"],
             available_delta, reserved_delta),
        )

    def audit(self, connection: sqlite3.Connection) -> dict:
        inventories = [dict(row) for row in connection.execute("SELECT * FROM inventory ORDER BY sku")]
        ledger = [dict(row) for row in connection.execute("SELECT * FROM inventory_ledger ORDER BY entry_id")]
        orders = [dict(row) for row in connection.execute("SELECT * FROM orders ORDER BY order_id")]
        checks = []
        for inventory in inventories:
            sku = inventory["sku"]
            entries = [entry for entry in ledger if entry["sku"] == sku]
            sku_orders = [order for order in orders if order["sku"] == sku]
            active_quantity = sum(order["quantity"] for order in sku_orders
                                  if order["reservation_state"] == "active")
            expected_available = inventory["initial_stock"] + sum(entry["available_delta"] for entry in entries)
            expected_reserved = sum(entry["reserved_delta"] for entry in entries)
            expected_committed = sum(entry["committed_delta"] for entry in entries)
            conservation = (inventory["available"] + inventory["reserved"] + inventory["committed"]
                            == inventory["initial_stock"])
            ledger_matches = (inventory["available"] == expected_available
                              and inventory["reserved"] == expected_reserved
                              and inventory["committed"] == expected_committed)
            order_matches = inventory["reserved"] == active_quantity
            legal_states = all(
                (order["status"] == "reserved" and order["reservation_state"] == "active")
                or (order["status"] == "created" and order["reservation_state"] == "none")
                or (order["status"] == "cancelled" and order["reservation_state"] in ("none", "released"))
                for order in sku_orders
            )
            order_ledger_matches = True
            for order in sku_orders:
                order_entries = [entry for entry in ledger if entry["order_id"] == order["order_id"]]
                expected_actions = {
                    "none": [], "active": ["reserve"], "released": ["reserve", "release"],
                }[order["reservation_state"]]
                order_ledger_matches = order_ledger_matches and (
                    [entry["action"] for entry in order_entries] == expected_actions
                    and all(entry["sku"] == sku and entry["quantity"] == order["quantity"]
                            for entry in order_entries)
                )
            checks.append({
                "sku": sku, "conservation": conservation, "ledger_matches": ledger_matches,
                "order_reservations_match": order_matches, "legal_order_states": legal_states,
                "order_ledger_matches": order_ledger_matches,
                "nonnegative": all(inventory[key] >= 0 for key in ("available", "reserved", "committed")),
            })
        consistent = all(all(value for key, value in check.items() if key != "sku") for check in checks)
        return {"consistent": consistent, "checks": checks, "inventory": inventories,
                "orders": orders, "ledger": ledger}
