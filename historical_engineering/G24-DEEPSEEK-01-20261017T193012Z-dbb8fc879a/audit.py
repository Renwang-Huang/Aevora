"""Trusted-host receipts for G24_DEEPSEEK_01."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


E = Path(__file__).resolve().parent
P = E / "worktree"
PRIVATE = Path("/home/PRIVATE_MAINTAINER/.config/aevora/g24-deepseek-01-dbb8fc879a")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _secret_values() -> list[bytes]:
    paths = [
        PRIVATE / "deepseek.token",
        *PRIVATE.glob("*.password"),
    ]
    values: list[bytes] = []
    for path in paths:
        if path.is_file():
            raw = path.read_bytes().strip()
            if len(raw) >= 16:
                values.extend((raw, base64.b64encode(raw), hashlib.sha256(raw).hexdigest().encode()))
    return values


def redact(data: bytes) -> bytes:
    for value in _secret_values():
        data = data.replace(value, b"[REDACTED_SECRET]")
    return data


def record(label: str, argv, *, cwd: Path | None = None, env: dict | None = None,
           timeout: float | None = None) -> int:
    destination = E / "commands" / label
    destination.mkdir(parents=True, exist_ok=False)
    started = now()
    monotonic = time.monotonic()
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=str(cwd or P),
        env=env,
        capture_output=True,
        timeout=timeout,
    )
    outputs = {}
    for name, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
        safe = redact(raw)
        (destination / f"{name}.log").write_bytes(safe)
        outputs[name] = {
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "safe_sha256": hashlib.sha256(safe).hexdigest(),
            "redacted": safe != raw,
            "bytes": len(safe),
        }
    receipt = {
        "argv": json.loads(redact(json.dumps([str(item) for item in argv]).encode())),
        "cwd": str(cwd or P),
        "start": started,
        "end": now(),
        "elapsed_seconds": time.monotonic() - monotonic,
        "exit": result.returncode,
        "outputs": outputs,
    }
    write(destination / "receipt.json", receipt)
    with (E / "COMMAND_LOG.jsonl").open("a") as log:
        log.write(json.dumps({"label": label, **receipt}, ensure_ascii=False) + "\n")
    return result.returncode


def environment(*, profile: str = "MODEL", live: bool = True) -> dict[str, str]:
    config = json.loads((E / f"RUNTIME_{profile}_CONFIG.json").read_text())
    result = {
        "HOME": "/tmp",
        "PATH": f"{config['venv']}/bin:/tools:/usr/bin",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
        "ORDERFLOW_BUILD_PROFILE": "MAINTAINER_ONLY",
        "ORDERFLOW_CGROUP_PARENT": config["cgroup"],
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": ":".join(
            [
                str(P / "aevora_core/src"),
                str(P / "console/src"),
                str(P),
            ]
        ),
        "GIT_OPTIONAL_LOCKS": "0",
        "AEVORA_FALKORDB_PASSWORD_FILE": "/maintainer/aevora-db.password",
        "AEVORA_FALKORDB_PORT": str(config["port"]),
        "AEVORA_FALKORDB_GRAPH": config["graph"],
        "AEVORA_FALKORDB_HOST": "127.0.0.1",
        "ORDERFLOW_CODEX_BINARY": str(E / "owned_runtime/native/codex"),
        "ORDERFLOW_GATEWAY_SECRET_PATH": "/maintainer/deepseek.token",
        "ORDERFLOW_GATEWAY_URL": "https://api.deepseek.com",
        "ORDERFLOW_ENABLE_CODEX": "1",
    }
    if live:
        result["AEVORA_RUN_TOKEN"] = "HOST_ONLY_NOT_EXPORTED"
    return result
