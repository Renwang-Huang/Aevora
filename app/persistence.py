"""SQLite persistence with one connection and transaction per public operation."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.errors import FixtureConflict, InvalidInput


SCHEMA_VERSION = 1
SQLITE_BUSY_TIMEOUT_SECONDS = 30.0

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS schema_metadata (
        version INTEGER NOT NULL CHECK (version = 1)
    )""",
    """CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT PRIMARY KEY,
        initial_stock INTEGER NOT NULL CHECK (initial_stock >= 0),
        available INTEGER NOT NULL CHECK (available >= 0),
        reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
        committed INTEGER NOT NULL DEFAULT 0 CHECK (committed >= 0),
        CHECK (available + reserved + committed = initial_stock)
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        sku TEXT NOT NULL REFERENCES inventory(sku),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        status TEXT NOT NULL CHECK (status IN ('created', 'reserved', 'cancelled')),
        reservation_state TEXT NOT NULL
            CHECK (reservation_state IN ('none', 'active', 'released')),
        CHECK (status != 'created' OR reservation_state = 'none'),
        CHECK (status != 'reserved' OR reservation_state = 'active')
    )""",
    """CREATE TABLE IF NOT EXISTS inventory_ledger (
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL REFERENCES orders(order_id),
        sku TEXT NOT NULL REFERENCES inventory(sku),
        action TEXT NOT NULL CHECK (action IN ('reserve', 'release')),
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        available_delta INTEGER NOT NULL,
        reserved_delta INTEGER NOT NULL,
        committed_delta INTEGER NOT NULL DEFAULT 0,
        UNIQUE (order_id, action),
        CHECK (available_delta + reserved_delta + committed_delta = 0),
        CHECK ((action = 'reserve' AND available_delta = -quantity
                  AND reserved_delta = quantity AND committed_delta = 0)
            OR (action = 'release' AND available_delta = quantity
                  AND reserved_delta = -quantity AND committed_delta = 0))
    )""",
    "CREATE INDEX IF NOT EXISTS orders_sku_idx ON orders(sku)",
    "CREATE INDEX IF NOT EXISTS ledger_sku_idx ON inventory_ledger(sku)",
)


def validate_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f"{name} must be a nonempty string")


def validate_quantity(quantity: int, *, allow_zero: bool = False) -> None:
    minimum = 0 if allow_zero else 1
    if type(quantity) is not int or quantity < minimum:
        raise InvalidInput(f"quantity must be an integer >= {minimum}")


class SQLitePersistence:
    """File-backed storage suitable for independent processes and later adapters."""

    def __init__(self, db_path: str | Path):
        if str(db_path) == ":memory:":
            raise InvalidInput("Use a file database; operations open independent connections")
        self.db_path = Path(db_path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=SQLITE_BUSY_TIMEOUT_SECONDS, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def initialize(self, stock: Mapping[str, int], *, reset: bool = False) -> None:
        if not isinstance(stock, Mapping):
            raise InvalidInput("stock must map SKU strings to nonnegative integers")
        for sku, quantity in stock.items():
            validate_identifier(sku, "sku")
            validate_quantity(quantity, allow_zero=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            if reset:
                for table in ("inventory_ledger", "orders", "inventory", "schema_metadata"):
                    connection.execute(f"DROP TABLE IF EXISTS {table}")
            for statement in _SCHEMA:
                connection.execute(statement)
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_metadata")]
            if versions and versions != [SCHEMA_VERSION]:
                raise FixtureConflict("Unsupported database schema version")
            if not versions:
                connection.execute("INSERT INTO schema_metadata(version) VALUES (?)", (SCHEMA_VERSION,))
                connection.executemany(
                    "INSERT INTO inventory(sku, initial_stock, available) VALUES (?, ?, ?)",
                    [(sku, quantity, quantity) for sku, quantity in sorted(stock.items())],
                )
            else:
                existing = {
                    row["sku"]: row["initial_stock"]
                    for row in connection.execute("SELECT sku, initial_stock FROM inventory")
                }
                if existing != dict(stock):
                    raise FixtureConflict("Fixture differs from initialized stock; use reset=True")
