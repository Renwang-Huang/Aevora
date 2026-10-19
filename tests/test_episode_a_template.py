"""Developer checks for the fixture construction and actual reference patch."""

from pathlib import Path
import shutil
import subprocess

import pytest

from benchmark.episodes.episode_a import (
    FIXTURE_VERSION, ROOT, create_episode_a, episode_a_reference_patch,
)
from benchmark.runner import apply_patch
from benchmark.sandbox import runtime_python, sandbox_command


def test_episode_a_preserves_database_constraints_and_transactions(tmp_path):
    workspace = create_episode_a(tmp_path / "candidate")
    assert FIXTURE_VERSION == "1.0.0"
    assert (workspace / "app" / "persistence.py").read_bytes() == (ROOT / "app" / "persistence.py").read_bytes()
    source = (workspace / "app" / "service.py").read_text()
    assert source.index("snapshot = self.get_inventory(sku)") < source.index(
        "with self.persistence.transaction() as connection:"
    )
    assert 'checkpoint("inventory_read")' in source
    inventory = (workspace / "app" / "inventory.py").read_text()
    assert '"UPDATE inventory SET available = ?, reserved = ? WHERE sku = ?"' in inventory
    assert 'self._record(connection, order, "reserve"' in inventory
    for name in ("orders.py", "errors.py", "contracts.py"):
        if (ROOT / "app" / name).exists():
            assert (workspace / "app" / name).read_bytes() == (ROOT / "app" / name).read_bytes()


def test_episode_a_reference_patch_restores_baseline(tmp_path):
    workspace = create_episode_a(tmp_path / "candidate")
    patch = tmp_path / "reference.diff"
    patch.write_text(episode_a_reference_patch())
    assert "a/app/service.py" in patch.read_text()
    assert "a/app/inventory.py" in patch.read_text()
    apply_patch(workspace, patch)
    for path in (ROOT / "app").rglob("*.py"):
        assert (workspace / "app" / path.relative_to(ROOT / "app")).read_bytes() == path.read_bytes()


def test_episode_a_correct_factory_copies_baseline(tmp_path):
    workspace = create_episode_a(tmp_path / "correct", buggy=False)
    for path in (ROOT / "app").rglob("*.py"):
        assert (workspace / "app" / path.relative_to(ROOT / "app")).read_bytes() == path.read_bytes()


def test_episode_a_rejects_unknown_fault_variant(tmp_path):
    with pytest.raises(ValueError, match="Unsupported Episode A"):
        create_episode_a(tmp_path / "invalid", variant="unknown")
    with pytest.raises(ValueError, match="Unsupported Episode A"):
        episode_a_reference_patch("unknown")
    assert not (tmp_path / "invalid").exists()


def test_episode_a_fault_keeps_single_thread_public_business_usable(tmp_path):
    workspace = create_episode_a(tmp_path / "candidate")
    public = workspace / "tests" / "public"
    public.mkdir(parents=True)
    shutil.copyfile(ROOT / "tests" / "public" / "test_episode_a.py", public / "test_episode_a.py")
    completed = subprocess.run(
        sandbox_command(workspace, [runtime_python(), "-B", "-m", "unittest", "discover",
                                    "-s", "tests/public"]),
        capture_output=True, text=True, timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Ran 2 tests" in completed.stderr
