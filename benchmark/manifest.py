"""Versioned, validated public scenario protocol, separate from private grading."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "benchmark" / "scenarios"


class Episode(Protocol):
    id: str
    version: str
    status: str
    metadata: dict
    runtime: dict
    initial_state: dict
    public_task: dict
    evaluation: dict


@dataclass(frozen=True)
class ScenarioManifest:
    id: str
    version: str
    status: str
    metadata: dict
    runtime: dict
    initial_state: dict
    public_task: dict
    evaluation: dict

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Manifest requires exactly the Episode protocol fields")
        if not isinstance(data["id"], str) or not re.fullmatch(r"[A-Z][A-Z0-9-]{0,63}", data["id"]):
            raise ValueError("Invalid Episode ID")
        if not isinstance(data["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", data["version"]):
            raise ValueError("Scenario version must be semver")
        if data["status"] not in ("PLANNED", "IMPLEMENTED"):
            raise ValueError("Invalid implementation status")
        for name in ("metadata", "runtime", "initial_state", "public_task", "evaluation"):
            if not isinstance(data[name], dict):
                raise ValueError(f"{name} must be an object")
        for key in ("title", "family", "research_role"):
            if not isinstance(data["metadata"].get(key), str) or not data["metadata"][key].strip():
                raise ValueError(f"Missing metadata.{key}")
        if data["runtime"].get("python") != "3.12" or data["runtime"].get("database") != "sqlite":
            raise ValueError("Phase 1 requires Python 3.12 and SQLite")
        if not isinstance(data["runtime"].get("topology"), str):
            raise ValueError("Missing runtime topology")
        task = data["public_task"]
        if not isinstance(task.get("description"), str) or not task["description"].strip():
            raise ValueError("Public task description is required")
        if not isinstance(task.get("constraints"), list) or not all(isinstance(c, str) for c in task["constraints"]):
            raise ValueError("Task constraints must be strings")
        ready = data["status"] == "IMPLEMENTED"
        if type(data["evaluation"].get("implemented")) is not bool or data["evaluation"]["implemented"] != ready:
            raise ValueError("Evaluation readiness contradicts Episode status")
        stock = data["initial_state"].get("stock")
        if ready and (not isinstance(stock, dict) or not stock):
            raise ValueError("Implemented Episode requires stock fixtures")
        if stock is not None and (not isinstance(stock, dict) or any(
            not isinstance(k, str) or not k.strip() or type(v) is not int or v < 0
            for k, v in stock.items()
        )):
            raise ValueError("Stock fixtures must be nonnegative integers")
        # No private suite paths, answer labels, or reference fix may enter this object.
        serialized = json.dumps(data).lower()
        if any(term in serialized for term in ("hidden_suite", "reference_patch", "fault_specification")):
            raise ValueError("Public manifest includes private evaluation fields")
        return cls(**data)


def load_manifest(episode: str) -> ScenarioManifest:
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{0,63}", episode):
        raise ValueError("Invalid Episode ID")
    path = SCENARIOS / episode / "public.json"
    data = json.loads(path.read_text())
    manifest = ScenarioManifest.from_dict(data)
    if manifest.id != episode:
        raise ValueError("Manifest ID does not match directory")
    return manifest


def list_manifests():
    return [load_manifest(path.parent.name) for path in sorted(SCENARIOS.glob("*/public.json"))]


def manifest_digest(manifest) -> str:
    from dataclasses import asdict
    return hashlib.sha256(json.dumps(asdict(manifest), sort_keys=True).encode()).hexdigest()


def private_config(episode: str) -> dict:
    public = load_manifest(episode)
    config = json.loads((ROOT / "evaluator" / "private_manifests" / f"{episode}.json").read_text())
    if not isinstance(config, dict):
        raise ValueError("Private manifest must be an object")
    if config.get("id") != public.id or config.get("version") != public.version:
        raise ValueError("Public/private manifest mismatch")
    if type(config.get("implemented")) is not bool or config["implemented"] != (public.status == "IMPLEMENTED"):
        raise ValueError("Private evaluation readiness mismatch")
    if config["implemented"]:
        timeout = config.get("timeout_seconds", 0)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("Evaluation timeout must be in (0, 120]")
        if type(config.get("expected_test_count")) is not int or config["expected_test_count"] < 1:
            raise ValueError("Expected hidden test count is required")
        from benchmark.registry import get_episode
        from evaluator.suites import get_suite
        registration = get_episode(episode)
        suite = get_suite(config.get("suite"))
        if registration.suite_id != suite.id or config.get("fixture_version") != registration.fixture_version:
            raise ValueError("Registered fixture/suite does not match private manifest")
        if config.get("execution_strategy", "single-worker") != registration.execution_strategy or suite.execution_strategy != registration.execution_strategy:
            raise ValueError("Registered execution strategy does not match private manifest/suite")
        if len(suite.expected_tests) != config["expected_test_count"]:
            raise ValueError("Expected test count and test identities do not match")
    return config
