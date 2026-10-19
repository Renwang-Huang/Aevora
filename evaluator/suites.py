"""Trusted suite selection and exact required test identities, per Episode."""
from dataclasses import dataclass
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class EvaluationSuite:
    id: str
    version: str
    path: Path
    manifest_episode: str
    execution_strategy: str = "single-worker"

    @property
    def expected_tests(self) -> tuple[str, ...]:
        config = json.loads((ROOT / "evaluator/private_manifests" / f"{self.manifest_episode}.json").read_text())
        tests = config.get("expected_tests")
        if not isinstance(tests, list) or not tests or len(set(tests)) != len(tests) or not all(isinstance(t, str) and t for t in tests):
            raise ValueError("Private manifest requires a nonempty unique test set")
        if config.get("suite") != self.id or config.get("suite_version") != self.version:
            raise ValueError("Suite version and private manifest do not match")
        return tuple(tests)


SUITES = {
    "smoke": EvaluationSuite("smoke", "2.0.0", ROOT / "evaluator/hidden_tests/test_smoke.py", "SMOKE-001"),
    "episode_a": EvaluationSuite("episode_a", "1.0.0", ROOT / "evaluator/hidden_tests/episode_a", "A"),
    "episode_d": EvaluationSuite("episode_d", "1.2.0", ROOT / "evaluator/hidden_tests/episode_d", "D",
                                 execution_strategy="shared-db-workers"),
}


def get_suite(suite_id: str) -> EvaluationSuite:
    try:
        return SUITES[suite_id]
    except KeyError as error:
        raise ValueError(f"Unregistered evaluation suite: {suite_id}") from error
