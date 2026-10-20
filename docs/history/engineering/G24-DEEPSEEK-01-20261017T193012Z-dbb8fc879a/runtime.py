"""Run trusted G24 host commands inside the pinned system-runtime namespace."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from audit import E, P, PRIVATE, record


V5_RUNTIME = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/"
    "V5C1-20261015T054437Z-fb77b23eff/owned_runtime/usr"
)
G23_EVIDENCE = Path(
    "/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/"
    "G23-20261016T021142Z-1e5e8e1af0"
)


def command(*args, profile: str = "MODEL", native: bool = False) -> list[str]:
    config = json.loads((E / f"RUNTIME_{profile}_CONFIG.json").read_text())
    result = [
        "bwrap",
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--ro-bind", str(V5_RUNTIME), "/usr",
        "--ro-bind", "/usr/bin/bwrap", "/tools/bwrap",
        "--ro-bind", "/usr/bin/git", "/tools/git",
        "--ro-bind", "/usr/bin/make", "/tools/make",
        "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
        "--ro-bind", "/etc/ssl/certs", "/etc/ssl/certs",
        "--bind", "/sys/fs/cgroup", "/sys/fs/cgroup",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/bin", "/bin",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--ro-bind", str(V5_RUNTIME), str(V5_RUNTIME),
        "--ro-bind", str(G23_EVIDENCE), str(G23_EVIDENCE),
        "--bind", str(E), str(E),
        "--ro-bind", config["password_file"], "/maintainer/aevora-db.password",
        "--ro-bind", str(PRIVATE / "deepseek.token"), "/maintainer/deepseek.token",
        "--chdir", str(P),
        "--clearenv",
    ]
    environment = {
        "HOME": "/tmp",
        "PATH": f"{config['venv']}/bin:/tools:/usr/bin",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
        "ORDERFLOW_BUILD_PROFILE": "MAINTAINER_ONLY",
        "ORDERFLOW_CGROUP_PARENT": config["cgroup"],
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": f"{P / 'aevora_core/src'}:{P / 'console/src'}:{P}",
        "GIT_OPTIONAL_LOCKS": "0",
        "AEVORA_FALKORDB_PASSWORD_FILE": "/maintainer/aevora-db.password",
        "AEVORA_FALKORDB_PORT": str(config["port"]),
        "AEVORA_FALKORDB_GRAPH": os.environ.get(
            "AEVORA_FALKORDB_GRAPH_OVERRIDE", config["graph"]
        ),
        "AEVORA_FALKORDB_HOST": "127.0.0.1",
        "ORDERFLOW_CODEX_BINARY": str(E / "owned_runtime/native/codex"),
        "ORDERFLOW_GATEWAY_SECRET_PATH": "/maintainer/deepseek.token",
        "ORDERFLOW_GATEWAY_URL": "https://api.deepseek.com",
        "ORDERFLOW_MODEL_CATALOG_PATH": str(E / "owned_runtime/deepseek-models.json"),
        "ORDERFLOW_ENABLE_CODEX": "1",
    }
    for key, value in environment.items():
        result.extend(["--setenv", key, value])
    for key in ("AEVORA_G24_AGENT_PROTOCOL", "AEVORA_G24_AGENT_MODE", "G24_TEST_WIRE_BUDGET"):
        if key in os.environ:
            result.extend(["--setenv", key, os.environ[key]])
    if native:
        result.extend(["--setenv", "ORDERFLOW_CODEX_BINARY", str(E / "owned_runtime/native/codex")])
    result.append(str(Path(config["venv"]) / "bin/python"))
    result.extend(str(item) for item in args)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("MODEL", "REGRESSION"), default="MODEL")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("label")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    args = parsed.args
    if args[:1] == ["--"]:
        args = args[1:]
    return record(
        parsed.label,
        command(*args, profile=parsed.profile, native=parsed.native),
        cwd=P,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"},
    )


if __name__ == "__main__":
    raise SystemExit(main())
