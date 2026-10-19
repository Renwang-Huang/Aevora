"""Order state transitions; the facade owns transaction boundaries."""

import sqlite3

from app.errors import InventoryNotFound, OrderConflict, OrderNotFound
from app.persistence import validate_identifier, validate_quantity


class OrderService:
    def get(self, connection: sqlite3.Connection, order_id: str) -> dict:
        validate_identifier(order_id, "order_id")
        row = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise OrderNotFound(order_id)
        return dict(row)

    def create(self, connection: sqlite3.Connection, order_id: str, sku: str, quantity: int) -> dict:
        validate_identifier(order_id, "order_id")
        validate_identifier(sku, "sku")
        validate_quantity(quantity)
        existing = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if existing is not None:
            if existing["sku"] != sku or existing["quantity"] != quantity:
                raise OrderConflict(f"Order {order_id!r} already has different contents")
            return dict(existing)
        if connection.execute("SELECT 1 FROM inventory WHERE sku = ?", (sku,)).fetchone() is None:
            raise InventoryNotFound(sku)
        connection.execute(
            "INSERT INTO orders(order_id, sku, quantity, status, reservation_state) "
            "VALUES (?, ?, ?, 'created', 'none')",
            (order_id, sku, quantity),
        )
        return self.get(connection, order_id)

    def mark_cancelled(self, connection: sqlite3.Connection, order_id: str) -> dict:
        self.get(connection, order_id)
        connection.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
        return self.get(connection, order_id)
