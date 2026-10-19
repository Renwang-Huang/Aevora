"""Real launcher refusal contracts; not a model or business challenge."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def invoke(tmp_path, *, password=None, port="17679", explicit_runtime=True):
    # Only failure-before-exec controls use this deliberately incomplete runtime.
    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True, exist_ok=True)
    python = runtime / "bin/python3.12"
    python.write_text("#!/bin/sh\nexit 91\n")
    python.chmod(0o700)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "AEVORA_FALKORDB_PORT": port, "AEVORA_FALKORDB_GRAPH": "aevora_test"}
    if explicit_runtime:
        env["AEVORA_H2_RUNTIME"] = str(runtime)
    if password is not None:
        env["AEVORA_FALKORDB_PASSWORD_FILE"] = str(password)
    return subprocess.run([str(ROOT / "scripts/aevora-h2-python"), "-c", "raise SystemExit(0)"],
                          env=env, capture_output=True, text=True, timeout=5)


def test_h2_launcher_requires_explicit_runtime(tmp_path):
    result = invoke(tmp_path, explicit_runtime=False)
    assert result.returncode != 0
    assert "AEVORA_H2_RUNTIME" in result.stderr


def test_h2_launcher_requires_external_password_path(tmp_path):
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert "AEVORA_FALKORDB_PASSWORD_FILE" in result.stderr


def test_h2_launcher_refuses_h1_endpoint(tmp_path):
    secret = tmp_path / "dedicated-test-secret"
    secret.write_text("DEDICATED_NONSECRET_NEGATIVE_CONTROL")
    secret.chmod(0o600)
    result = invoke(tmp_path, password=secret, port="16379")
    assert result.returncode == 2
    assert "Refusing H1" in result.stderr
    assert secret.read_text() not in result.stdout + result.stderr


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "world-readable", "fifo", "directory", "missing"])
def test_h2_launcher_rejects_unsafe_credential_without_reading(tmp_path, kind):
    original = tmp_path / "dedicated-control"
    original.write_text("DEDICATED_NONSECRET_NEGATIVE_CONTROL")
    original.chmod(0o600)
    target = tmp_path / "input"
    if kind == "symlink":
        target.symlink_to(original)
    elif kind == "hardlink":
        os.link(original, target)
    elif kind == "world-readable":
        target.write_text(original.read_text())
        target.chmod(0o644)
    elif kind == "fifo":
        os.mkfifo(target, 0o600)
    elif kind == "directory":
        target.mkdir()
    result = invoke(tmp_path, password=target)
    assert result.returncode == 2
    assert "credential" in result.stderr.lower()
    assert original.read_text() not in result.stdout + result.stderr


def test_h2_release_source_allowlist_includes_extensionless_launcher():
    from hashlib import sha256
    from scripts.aevora_h2_audit import ROOT, sources

    launcher = ROOT / "scripts/aevora-h2-python"
    row = sources()["scripts/aevora-h2-python"]
    assert row["sha256"] == sha256(launcher.read_bytes()).hexdigest()
    assert row["mode"] & 0o111
