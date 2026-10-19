"""Public, JSON-serializable order/inventory API used by runners and clients."""

from pathlib import Path

from app.errors import InvalidInput
from app.inventory import InventoryService
from app.orders import OrderService
from app.persistence import SQLitePersistence


class OrderFlow:
    def __init__(self, db_path: str | Path):
        self.persistence = SQLitePersistence(db_path)
        self.orders = OrderService()
        self.inventory = InventoryService(self.orders)

    def initialize(self, stock: dict[str, int], reset: bool = False) -> None:
        self.persistence.initialize(stock, reset=reset)

    def create_order(self, order_id: str, sku: str, quantity: int, *, reserve: bool = True) -> dict:
        if type(reserve) is not bool:
            raise InvalidInput("reserve must be a boolean")
        with self.persistence.transaction() as connection:
            order = self.orders.create(connection, order_id, sku, quantity)
            if reserve and order["status"] == "created":
                order = self.inventory.reserve(connection, order_id)
            return order

    def reserve_inventory(self, order_id: str) -> dict:
        with self.persistence.transaction() as connection:
            return self.inventory.reserve(connection, order_id)

    def cancel_order(self, order_id: str) -> dict:
        with self.persistence.transaction() as connection:
            self.orders.mark_cancelled(connection, order_id)
            return self.inventory.release(connection, order_id)

    def release_inventory(self, order_id: str) -> dict:
        with self.persistence.transaction() as connection:
            return self.inventory.release(connection, order_id)

    def get_order(self, order_id: str) -> dict:
        with self.persistence.connection() as connection:
            return self.orders.get(connection, order_id)

    def get_inventory(self, sku: str) -> dict:
        with self.persistence.connection() as connection:
            return self.inventory.get(connection, sku)

    def audit(self) -> dict:
        with self.persistence.connection() as connection:
            connection.execute("BEGIN")
            return self.inventory.audit(connection)
