"""Episode A fixture: a stale inventory snapshot crossing a transaction boundary.

The source schema and transaction implementation remain unchanged. The defect
comes from computing absolute inventory values from a read that happened before
the reservation transaction. Concurrent orders can each commit a valid row and
ledger entry while losing another order's inventory change.
"""

import difflib
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_VERSION = "1.0.0"
FAULT_VARIANT = "stale-snapshot"

_CREATE_START = '''        with self.persistence.transaction() as connection:
            order = self.orders.create(connection, order_id, sku, quantity)
'''
_STALE_CREATE_START = '''        # Fetch stock before opening the write transaction so reads stay cheap.
        snapshot = self.get_inventory(sku) if reserve else None
        if snapshot is not None:
            checkpoint = getattr(self, "_schedule_checkpoint", None)
            if checkpoint is not None:
                checkpoint("inventory_read")
        with self.persistence.transaction() as connection:
            order = self.orders.create(connection, order_id, sku, quantity)
'''
_RESERVE_CALL = '                order = self.inventory.reserve(connection, order_id)\n'
_STALE_RESERVE_CALL = '                order = self.inventory.reserve(connection, order_id, snapshot=snapshot)\n'
_RESERVE_SIGNATURE = '    def reserve(self, connection: sqlite3.Connection, order_id: str) -> dict:\n'
_STALE_RESERVE_SIGNATURE = ('    def reserve(self, connection: sqlite3.Connection, order_id: str, *,\n'
                            '                snapshot: dict | None = None) -> dict:\n')
_ATOMIC_UPDATE = '''        cursor = connection.execute(
            "UPDATE inventory SET available = available - ?, reserved = reserved + ? "
            "WHERE sku = ? AND available >= ?",
            (order["quantity"], order["quantity"], order["sku"], order["quantity"]),
        )
        if cursor.rowcount != 1:
            raise InsufficientInventory(order["sku"])
'''
_SNAPSHOT_UPDATE = '''        if snapshot is None:
            cursor = connection.execute(
                "UPDATE inventory SET available = available - ?, reserved = reserved + ? "
                "WHERE sku = ? AND available >= ?",
                (order["quantity"], order["quantity"], order["sku"], order["quantity"]),
            )
            if cursor.rowcount != 1:
                raise InsufficientInventory(order["sku"])
        else:
            if snapshot["available"] < order["quantity"]:
                raise InsufficientInventory(order["sku"])
            connection.execute(
                "UPDATE inventory SET available = ?, reserved = ? WHERE sku = ?",
                (snapshot["available"] - order["quantity"],
                 snapshot["reserved"] + order["quantity"], order["sku"]),
            )
'''


def _check_variant(variant: str) -> None:
    if variant != FAULT_VARIANT:
        raise ValueError(f"Unsupported Episode A fault variant: {variant!r}")


def _replace_once(source: str, original: str, replacement: str, label: str) -> str:
    if source.count(original) != 1:
        raise RuntimeError(f"Episode A template no longer matches the business baseline: {label}")
    return source.replace(original, replacement, 1)


def _fault_sources(variant: str) -> dict[str, str]:
    _check_variant(variant)
    service = (ROOT / "app" / "service.py").read_text()
    service = _replace_once(service, _CREATE_START, _STALE_CREATE_START, "create transaction")
    service = _replace_once(service, _RESERVE_CALL, _STALE_RESERVE_CALL, "reservation call")
    inventory = (ROOT / "app" / "inventory.py").read_text()
    inventory = _replace_once(inventory, _RESERVE_SIGNATURE, _STALE_RESERVE_SIGNATURE,
                              "reservation signature")
    inventory = _replace_once(inventory, _ATOMIC_UPDATE, _SNAPSHOT_UPDATE, "inventory update")
    return {"service.py": service, "inventory.py": inventory}


def create_episode_a(destination: Path, *, variant: str = FAULT_VARIANT,
                     buggy: bool = True) -> Path:
    """Copy the baseline app and optionally introduce the selected actual defect."""
    _check_variant(variant)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "app", destination / "app",
                    ignore=shutil.ignore_patterns("__pycache__"))
    if buggy:
        for name, source in _fault_sources(variant).items():
            (destination / "app" / name).write_text(source)
    return destination


def episode_a_reference_patch(variant: str = FAULT_VARIANT) -> str:
    """Generate the real patch from the selected faulty source to the baseline."""
    lines = []
    for name, buggy in _fault_sources(variant).items():
        correct = (ROOT / "app" / name).read_text()
        lines.extend(difflib.unified_diff(
            buggy.splitlines(keepends=True), correct.splitlines(keepends=True),
            fromfile=f"a/app/{name}", tofile=f"b/app/{name}",
        ))
    return "".join(lines)
