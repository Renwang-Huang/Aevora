"""Trusted Episode D fixtures and strategy artifacts.

The incident starts with a service that coordinates its own writers with a
process-local lock and calculates a reservation from an earlier stock read.
Independent workers do not coordinate that read/modify/write operation.  The
original schema and SQLite transaction implementation are retained.

Only the resulting ``app`` tree is public.  This factory, strategy names,
reference generation and applicability analysis remain on the trusted host.
"""

import difflib
from pathlib import Path
import shutil

from benchmark.episodes.episode_a import _fault_sources, _replace_once


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_VERSION = "1.0.0"
FAULT_VARIANT = "v01"
STRATEGIES = ("buggy", "reference", "flock", "local-lock-only", "split-ledger")


_LOCAL_GUARD = '''

# Keep writer operations coordinated inside this service process.
import functools
import threading

_process_write_lock = threading.RLock()

def _coordinate_write(method):
    @functools.wraps(method)
    def coordinated(self, *args, **kwargs):
        with _process_write_lock:
            return method(self, *args, **kwargs)
    return coordinated

for _method_name in ("initialize", "create_order", "reserve_inventory",
                     "cancel_order", "release_inventory"):
    setattr(OrderFlow, _method_name,
            _coordinate_write(getattr(OrderFlow, _method_name)))
'''

_FILE_GUARD = '''

# Coordinate the complete writer operation using the shared database's lock.
import fcntl
import functools
import threading

_process_write_lock = threading.RLock()

def _coordinate_write(method):
    @functools.wraps(method)
    def coordinated(self, *args, **kwargs):
        with _process_write_lock:
            self.persistence.db_path.parent.mkdir(parents=True, exist_ok=True)
            # The file is stable: unlinking it would create independent locks.
            # Open separately for each operation rather than inherit one fd.
            with open(str(self.persistence.db_path) + ".write.lock", "a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    return method(self, *args, **kwargs)
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return coordinated

for _method_name in ("initialize", "create_order", "reserve_inventory",
                     "cancel_order", "release_inventory"):
    setattr(OrderFlow, _method_name,
            _coordinate_write(getattr(OrderFlow, _method_name)))
'''

_CREATE = '''        with self.persistence.transaction() as connection:
            order = self.orders.create(connection, order_id, sku, quantity)
            if reserve and order["status"] == "created":
                order = self.inventory.reserve(connection, order_id)
            return order
'''

_SPLIT_CREATE = '''        with self.persistence.transaction() as connection:
            order = self.orders.create(connection, order_id, sku, quantity)
            newly_reserved = reserve and order["status"] == "created"
            if newly_reserved:
                order = self.inventory.reserve(connection, order_id, record=False)
        # Keep accounting writes in a separate transaction after the order.
        if newly_reserved:
            with self.persistence.transaction() as connection:
                self.inventory._record(connection, order, "reserve",
                                       -order["quantity"], order["quantity"])
        return order
'''


def _check(variant: str, strategy: str = "buggy") -> None:
    if variant != FAULT_VARIANT:
        raise ValueError(f"Unsupported Episode D variant: {variant!r}")
    if strategy not in STRATEGIES:
        raise ValueError(f"Unsupported Episode D strategy: {strategy!r}")


def _strategy_sources(strategy: str, variant: str = FAULT_VARIANT) -> dict[str, str]:
    _check(variant, strategy)
    if strategy in ("buggy", "local-lock-only", "flock"):
        sources = _fault_sources("stale-snapshot")
        sources["service.py"] += _FILE_GUARD if strategy == "flock" else _LOCAL_GUARD
        return sources
    if strategy == "reference":
        return {name: (ROOT / "app" / name).read_text()
                for name in ("service.py", "inventory.py")}

    service = (ROOT / "app" / "service.py").read_text()
    service = _replace_once(service, _CREATE, _SPLIT_CREATE, "split-ledger create")
    inventory = (ROOT / "app" / "inventory.py").read_text()
    inventory = _replace_once(
        inventory,
        "    def reserve(self, connection: sqlite3.Connection, order_id: str) -> dict:\n",
        "    def reserve(self, connection: sqlite3.Connection, order_id: str, *,\n"
        "                record: bool = True) -> dict:\n",
        "split-ledger reservation signature",
    )
    inventory = _replace_once(
        inventory,
        '        self._record(connection, order, "reserve", -order["quantity"], order["quantity"])\n',
        '        if record:\n'
        '            self._record(connection, order, "reserve", -order["quantity"], order["quantity"])\n',
        "split-ledger accounting write",
    )
    return {"service.py": service + _LOCAL_GUARD, "inventory.py": inventory}


def build_episode_d_fixture(workspace: Path, variant: str = FAULT_VARIANT, *,
                            strategy: str = "buggy") -> Path:
    """Build an independent app-only fixture and return its workspace path.

    ``local-lock-only`` intentionally names the same artifact as ``buggy``.
    It is evaluated as a workspace, never represented by a fabricated patch.
    Other strategies differ from this exact defect baseline.
    """
    _check(variant, strategy)
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "app", workspace / "app",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name, source in _strategy_sources(strategy, variant).items():
        (workspace / "app" / name).write_text(source, encoding="utf-8")
    return workspace


def episode_d_patch(strategy: str = "reference", variant: str = FAULT_VARIANT) -> str:
    """Return a real nonempty repair/mutant diff against the D defect baseline."""
    _check(variant, strategy)
    if strategy in ("buggy", "local-lock-only"):
        raise ValueError("The local-lock-only baseline must be evaluated as a workspace")
    baseline = _strategy_sources("buggy", variant)
    target = _strategy_sources(strategy, variant)
    lines = []
    for name in sorted(baseline.keys() | target.keys()):
        original = baseline.get(name, (ROOT / "app" / name).read_text())
        repaired = target.get(name, (ROOT / "app" / name).read_text())
        lines.extend(difflib.unified_diff(
            original.splitlines(keepends=True), repaired.splitlines(keepends=True),
            fromfile=f"a/app/{name}", tofile=f"b/app/{name}",
        ))
    return "".join(lines)


def episode_d_reference_patch(variant: str = FAULT_VARIANT) -> str:
    return episode_d_patch("reference", variant)


def episode_d_alternative_patch(variant: str = FAULT_VARIANT) -> str:
    return episode_d_patch("flock", variant)
