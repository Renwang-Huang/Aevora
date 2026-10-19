"""Owned G24 task instances; original suites and references remain untouched.

Instances are real code/configuration variants within the already registered
A, D-v01 and D-v02 families. No old Oracle, expected test identity or public
task assertion is modified.
"""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path


PARTIAL_READ_GUARD = '''

import threading
_snapshot_read_guard = threading.RLock()
_read_inventory_unlocked = OrderFlow.get_inventory
def _read_inventory_guarded(self, *args, **kwargs):
    with _snapshot_read_guard:
        return _read_inventory_unlocked(self, *args, **kwargs)
OrderFlow.get_inventory = _read_inventory_guarded
'''


def build(destination, instance, *, implementation="buggy"):
    from benchmark.episodes.episode_a import create_episode_a
    from benchmark.episodes.episode_d import build_episode_d_fixture
    from benchmark.episodes.episode_d_v02 import build_episode_d_v02

    episode = instance["episode"]
    fault = instance["fault"]
    target = Path(destination)
    if episode == "A":
        create_episode_a(target, buggy=implementation == "buggy")
        if implementation == "buggy" and fault == "read-only-lock":
            service = target / "app/service.py"
            service.write_text(service.read_text() + PARTIAL_READ_GUARD)
    elif episode == "D":
        strategy = fault if implementation == "buggy" else implementation
        build_episode_d_fixture(target, strategy=strategy)
    elif episode == "D-V02":
        strategy = fault if implementation == "buggy" else implementation
        build_episode_d_v02(target, implementation=strategy)
    else:
        raise ValueError("Unregistered experiment family")

    persistence = target / "app/persistence.py"
    source = persistence.read_text()
    if instance["journal"] == "WAL":
        marker = "        self.db_path.parent.mkdir(parents=True, exist_ok=True)\n"
        assert source.count(marker) == 1
        source = source.replace(
            marker,
            marker
            + "        with self.connection() as journal_connection:\n"
            + '            journal_connection.execute("PRAGMA journal_mode = WAL")\n',
        )
    assert source.count("SQLITE_BUSY_TIMEOUT_SECONDS = 30.0") == 1
    source = source.replace(
        "SQLITE_BUSY_TIMEOUT_SECONDS = 30.0",
        f"SQLITE_BUSY_TIMEOUT_SECONDS = {float(instance['busy_timeout'])}",
    )
    persistence.write_text(source)
    return target


@contextmanager
def bind(instance):
    """Bind one pre-registered instance to the unchanged Runner/Evaluator."""
    from benchmark import registry
    from benchmark.h2_cli import register_h2

    register_h2()
    episode = instance["episode"]
    old = registry.REGISTRY[episode]
    registry.REGISTRY[episode] = replace(
        old,
        fixture_factory=lambda destination, variant: build(destination, instance),
    )
    try:
        yield
    finally:
        registry.REGISTRY[episode] = old
