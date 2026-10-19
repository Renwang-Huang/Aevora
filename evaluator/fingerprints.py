"""Evidence fingerprints computed from real source bytes and installed tools."""
import hashlib
import importlib.metadata
import platform
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_VERSION = "3.1.0"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(paths) -> dict:
    files = sorted({p for path in paths for p in ([path] if path.is_file() else path.rglob("*.py"))
                    if p.is_file() and "__pycache__" not in p.parts})
    hashes = {p.relative_to(ROOT).as_posix(): file_sha256(p) for p in files}
    digest = hashlib.sha256()
    for name, sha in hashes.items():
        digest.update(name.encode() + b"\0" + sha.encode() + b"\n")
    return {"sha256": digest.hexdigest(), "files": hashes}


def runtime_versions() -> dict:
    tools = {}
    for name in ("bwrap", "git"):
        executable = shutil.which(name)
        if executable:
            process = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5)
            tools[name] = {"version": process.stdout.strip(), "exit_code": process.returncode,
                           "executable_sha256": file_sha256(Path(executable))}
        else:
            tools[name] = {"version": None, "availability": "UNAVAILABLE"}
    return {"python": sys.version, "sqlite": sqlite3.sqlite_version,
            "python_executable_sha256": file_sha256(Path(sys.executable).resolve()),
            "platform": platform.platform(), "packages": {n: importlib.metadata.version(n) for n in ("pytest", "pluggy")},
            "tools": tools}


def evaluation_fingerprints(episode, registration, config):
    from evaluator.suites import get_suite
    suite = get_suite(config["suite"])
    result = {"evaluator": {"version": EVALUATOR_VERSION, **source_digest([ROOT / "evaluator", ROOT / "benchmark/sandbox.py"])},
            "private_manifest_sha256": file_sha256(ROOT / "evaluator/private_manifests" / f"{episode}.json"),
            "fixture": {"version": registration.fixture_version,
                        **source_digest([ROOT / "app", ROOT / "benchmark/templates.py", ROOT / "benchmark/episodes", ROOT / "benchmark/registry.py"])},
            "test_suite": {"id": suite.id, "version": suite.version,
                           **source_digest([suite.path, ROOT / "evaluator/hidden_tests/conftest.py", ROOT / "evaluator/oracle.py"])},
            "execution_strategy": registration.execution_strategy,
            "runtime": runtime_versions()}
    label_name = config.get("decision_reference")
    if label_name is not None:
        # A separately versioned maintainer reference, never an engineering score.
        if not isinstance(label_name, str) or Path(label_name).name != label_name:
            raise ValueError("Invalid private decision reference")
        result["decision_reference"] = {"availability": "REFERENCE-ONLY", "file": label_name,
            "sha256": file_sha256(ROOT / "evaluator/private_labels" / label_name)}
    return result
