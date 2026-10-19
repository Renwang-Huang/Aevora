"""Fresh owned MODEL/REGRESSION databases for G24_DEEPSEEK_01."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess

from audit import E, P, PRIVATE, now, record, sha, write
from runtime import command


ACTIVE = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/"
    "G24-20261017T171230Z-83700e0a59"
)
G23 = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/"
    "G23-20261016T021142Z-1e5e8e1af0"
)
CODEX_ROOT = Path("/home/PRIVATE_MAINTAINER/.codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl/bin")
IMAGE = "falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62"
PORTS = {"MODEL": 18062, "REGRESSION": 18063}


def free(port: int) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def main() -> int:
    if (E / "venv").exists() or PRIVATE.exists():
        raise SystemExit("SETUP_ALREADY_STARTED")
    PRIVATE.mkdir(mode=0o700)
    shutil.copytree(G23 / "venv", E / "venv", symlinks=True)
    native = E / "owned_runtime/native"
    native.mkdir(parents=True)
    shutil.copy2(CODEX_ROOT / "codex", native / "codex")
    shutil.copy2(CODEX_ROOT / "codex-code-mode-host", native / "codex-code-mode-host")

    token_result = subprocess.run(
        ["/usr/bin/python3", "/home/PRIVATE_MAINTAINER/.config/codex1-gateway/get-deepseek-token.py"],
        capture_output=True,
        check=True,
        timeout=20,
    )
    token = token_result.stdout.strip()
    if not token or b"\n" in token or len(token) > 10000:
        raise SystemExit("DEEPSEEK_TOKEN_INVALID")
    token_path = PRIVATE / "deepseek.token"
    token_path.write_bytes(token + b"\n")
    token_path.chmod(0o600)

    cgroup = json.loads((ACTIVE / "RUNTIME_MODEL_CONFIG.json").read_text())["cgroup"]
    runtime_root = str(Path(__file__).resolve().parent)
    for profile in ("MODEL", "REGRESSION"):
        port = PORTS[profile]
        free(port)
        password_path = PRIVATE / f"{profile.lower()}.password"
        password_path.write_text(secrets.token_urlsafe(32) + "\n")
        password_path.chmod(0o600)
        config_path = PRIVATE / f"{profile.lower()}.conf"
        config_path.write_text(
            "bind 0.0.0.0\n"
            "protected-mode yes\n"
            f"requirepass {password_path.read_text().strip()}\n"
            "dir /data\n"
            'save ""\n'
            "appendonly no\n"
        )
        config_path.chmod(0o600)
        data = E / f"{profile.lower()}-db-data"
        data.mkdir(mode=0o700)
        config = {
            "profile": profile,
            "container": f"aevora-g24-deepseek-01-{profile.lower()}",
            "port": port,
            "password_file": str(password_path),
            "configuration_file": str(config_path),
            "graph": f"aevora_g24_deepseek_01_{profile.lower()}",
            "resource_limit": "2g" if profile == "MODEL" else "4g",
            "venv": str(E / "venv"),
            "runtime_root": runtime_root,
            "cgroup": cgroup,
            "image": IMAGE,
        }
        write(E / f"RUNTIME_{profile}_CONFIG.json", config)
        args = [
            "docker", "run", "-d",
            "--name", config["container"],
            "--label", "aevora.audit.owner=" + E.name,
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev",
            "--memory", config["resource_limit"],
            "--cpus", "2",
            "--pids-limit", "256",
            "-p", f"127.0.0.1:{port}:6379",
            "--mount", f"type=bind,src={config['configuration_file']},dst=/run/redis.conf,readonly",
            "--mount", f"type=bind,src={data},dst=/data",
            "--entrypoint", "redis-server",
            IMAGE,
            "--loadmodule", "/var/lib/falkordb/bin/falkordb.so",
            "--include", "/run/redis.conf",
        ]
        if record(f"start-{profile}", args) != 0:
            raise SystemExit(f"DATABASE_START_FAILED_{profile}")

    checks = []
    for profile in ("MODEL", "REGRESSION"):
        code = (
            "from aevora.graph_repository import GraphRepository;"
            "r=GraphRepository.from_environment();"
            "print(r._client.connection.info('server')['redis_version']);"
            "print(r._client.connection.execute_command('MODULE','LIST'));"
            "print(r.state_fingerprint());"
            "r.close()"
        )
        checks.append(record(f"db-health-{profile}", command("-c", code, profile=profile)))
    if any(checks):
        raise SystemExit("DATABASE_HEALTH_FAILED")
    if record(
        "editable-install",
        command(
            "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation",
            "-e", P, "-e", P / "aevora_core", "-e", P / "console",
            profile="REGRESSION",
        ),
    ) != 0:
        raise SystemExit("EDITABLE_INSTALL_FAILED")
    for label, args in (
        ("runtime-versions", ("-c", "import sys,sqlite3,importlib.metadata as m;print(sys.version);print(sqlite3.sqlite_version);print({k:m.version(k) for k in ['falkordb','redis','pytest','mcp','aevora-core']})")),
        ("pip-check", ("-m", "pip", "check")),
        ("runner-help", ("-m", "benchmark.cli", "run-codex", "--help")),
    ):
        if record(label, command(*args, profile="REGRESSION")) != 0:
            raise SystemExit(f"RUNTIME_CHECK_FAILED_{label}")
    if record(
        "native-version",
        command("-c", "import subprocess,os;raise SystemExit(subprocess.call([os.environ['ORDERFLOW_CODEX_BINARY'],'--version']))", profile="REGRESSION", native=True),
    ) != 0:
        raise SystemExit("NATIVE_VERSION_FAILED")
    write(E / "00_baseline/SETUP_RESULT.json", {
        "status": "PASS",
        "created": now(),
        "model_requests": 0,
        "databases": ["MODEL", "REGRESSION"],
        "codex_version": "0.163.0",
        "provider": "deepseek",
        "model": "deepseek-flash",
        "private_credential_values_recorded": False,
    })
    print(json.dumps(json.loads((E / "00_baseline/SETUP_RESULT.json").read_text()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
