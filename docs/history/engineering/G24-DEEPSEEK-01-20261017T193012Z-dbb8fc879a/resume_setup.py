"""Continue D1 after the first interpreter-path probe failed."""
from __future__ import annotations

import json

from audit import E, P, now, record, write
from runtime import command


def main() -> int:
    if not ((E / "venv/bin/python").is_symlink() or (E / "venv/bin/python").exists()):
        raise SystemExit("VENV_MISSING")
    for profile in ("MODEL", "REGRESSION"):
        code = (
            "from aevora.graph_repository import GraphRepository;"
            "r=GraphRepository.from_environment();"
            "print(r._client.connection.info('server')['redis_version']);"
            "print(r._client.connection.execute_command('MODULE','LIST'));"
            "print(r._client.connection.execute_command('GRAPH.LIST'));"
            "r.close()"
        )
        if record(f"db-health-{profile}-retry2", command("-c", code, profile=profile)) != 0:
            raise SystemExit(f"DATABASE_HEALTH_FAILED_{profile}")
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
        "prior_attempts_preserved": [
            "interpreter path mismatch",
            "uninitialized graph state probe rejected by real FalkorDB",
        ],
        "private_credential_values_recorded": False,
    })
    print(json.dumps(json.loads((E / "00_baseline/SETUP_RESULT.json").read_text()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
