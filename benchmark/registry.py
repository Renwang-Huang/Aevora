"""Small, trusted Episode registry: fixture, variant, public tests and suite.

Runner lifecycle does not contain Episode-specific branches. Factories and
suite definitions remain on the host and are never copied to Agent workspaces.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from benchmark.manifest import ROOT
from benchmark.templates import create_template
from benchmark.episodes.episode_a import create_episode_a
from benchmark.episodes.episode_d import build_episode_d_fixture


@dataclass(frozen=True)
class EpisodeRegistration:
    episode_id: str
    fixture_version: str
    suite_id: str
    default_variant: str
    variants: tuple[str, ...]
    fixture_factory: Callable
    public_tests: tuple[Path, ...]
    execution_strategy: str = "single-worker"

    def build(self, destination: Path, variant: str | None = None):
        selected = variant or self.default_variant
        if selected not in self.variants:
            raise ValueError(f"Unknown {self.episode_id} variant: {selected}")
        return self.fixture_factory(destination, selected)


def _smoke(destination, variant):
    return create_template(destination, buggy=True)


def _episode_a(destination, variant):
    return create_episode_a(destination, variant="stale-snapshot", buggy=True)


REGISTRY: dict[str, EpisodeRegistration] = {}


def register_episode(registration: EpisodeRegistration):
    if registration.episode_id in REGISTRY:
        raise ValueError(f"Duplicate Episode registration: {registration.episode_id}")
    if registration.default_variant not in registration.variants:
        raise ValueError("Default variant is not registered")
    if registration.execution_strategy not in {"single-worker", "shared-db-workers"}:
        raise ValueError("Unknown candidate execution strategy")
    REGISTRY[registration.episode_id] = registration


def get_episode(episode: str) -> EpisodeRegistration:
    try:
        return REGISTRY[episode]
    except KeyError as error:
        raise ValueError(f"Implemented Episode has no registered factory: {episode}") from error


register_episode(EpisodeRegistration("SMOKE-001", "1.0.0", "smoke", "default", ("default",),
                                   _smoke, (ROOT / "benchmark/public_tests/test_orders.py",)))
register_episode(EpisodeRegistration("A", "1.0.0", "episode_a", "v01", ("v01",),
                                   _episode_a, (ROOT / "benchmark/public_tests/test_episode_a.py",)))
register_episode(EpisodeRegistration("D", "1.0.0", "episode_d", "v01", ("v01",),
                                   build_episode_d_fixture, (ROOT / "benchmark/public_tests/test_episode_d.py",),
                                   execution_strategy="shared-db-workers"))
