"""Developer baseline and a deterministic Smoke-only defective variant."""
import difflib
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
GUARD = '        if order["reservation_state"] != "active":\n            return order\n'
BUG = '''        if order["reservation_state"] != "active":
            connection.execute(
                "UPDATE inventory SET available = available + ? WHERE sku = ?",
                (order["quantity"], order["sku"]),
            )
            return order
'''
CHECK = ',\n        CHECK (available + reserved + committed = initial_stock)'


def create_template(destination: Path, *, buggy=True) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "app", destination / "app", ignore=shutil.ignore_patterns("__pycache__"))
    if buggy:
        inventory = destination / "app" / "inventory.py"
        original = inventory.read_text()
        if original.count(GUARD) != 1:
            raise RuntimeError("Smoke template no longer matches the business baseline")
        inventory.write_text(original.replace(GUARD, BUG))
        persistence = destination / "app" / "persistence.py"
        original = persistence.read_text()
        if original.count(CHECK) != 1:
            raise RuntimeError("Smoke schema no longer matches the business baseline")
        persistence.write_text(original.replace(CHECK, ""))
    return destination


def reference_patch() -> str:
    result = []
    for name, old, new in (("inventory.py", BUG, GUARD), ("persistence.py", "", CHECK)):
        correct = (ROOT / "app" / name).read_text()
        buggy = correct.replace(GUARD, BUG) if name == "inventory.py" else correct.replace(CHECK, "")
        result.extend(difflib.unified_diff(buggy.splitlines(keepends=True), correct.splitlines(keepends=True),
                                          fromfile=f"a/app/{name}", tofile=f"b/app/{name}"))
    return "".join(result)
