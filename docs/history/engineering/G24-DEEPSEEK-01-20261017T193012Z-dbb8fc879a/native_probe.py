"""Minimal non-scored Codex native parent/child probe with MCP isolated."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from audit import E, write


PROMPT = (
    "This is a minimal non-scored native identity probe. Spawn exactly one child "
    "agent with task_name probe_child and message: 'Read README.md and return "
    "CHILD_OK. Do not spawn agents.' Wait for that exact child. If it returns a "
    "terminal result, report it. Do not modify files and do not start other work."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("protocol", choices=("v1", "v2"))
    parser.add_argument("--tag", default=None,
                        help="optional suffix for an independent probe directory")
    parser.add_argument("--timeout", type=float, default=300,
                        help="wall-clock timeout in seconds")
    parser.add_argument("--prompt", default=PROMPT,
                        help="prompt used for this non-scored identity probe")
    parser.add_argument("--max-agent-threads", type=int, default=8,
                        help="native per-session agent thread budget")
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    base = E / "09_evidence" / f"native_probe_{args.protocol}{suffix}"
    home = base / "codex_home"
    workspace = base / "workspace"
    base.mkdir(parents=True, exist_ok=False)
    home.mkdir(mode=0o700)
    workspace.mkdir(mode=0o700)
    (workspace / "README.md").write_text("demo\n")
    shutil.copy2(E / "owned_runtime/deepseek-models.json", home / "deepseek-models.json")
    config = f'''model = "deepseek-flash"
model_provider = "deepseek"
model_reasoning_effort = "max"
model_catalog_json = {json.dumps(str(home / "deepseek-models.json"))}

[agents]
enabled = true
max_concurrent_threads_per_session = {args.max_agent_threads}

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false

[model_providers.deepseek.auth]
command = "/home/PRIVATE_MAINTAINER/.config/codex1-gateway/get-deepseek-token.py"
timeout_ms = 5000
refresh_interval_ms = 300000

[projects.{json.dumps(str(workspace))}]
trust_level = "trusted"
'''
    (home / "config.toml").write_text(config)
    (workspace / ".keep").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True,
                   env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull})
    subprocess.run(["git", "add", "README.md", ".keep"], cwd=workspace, check=True,
                   env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull,
                        "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@invalid",
                        "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@invalid"})
    subprocess.run(["git", "commit", "-q", "-m", "probe"], cwd=workspace, check=True,
                   env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull,
                        "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@invalid",
                        "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@invalid"})
    command = [
        "/home/PRIVATE_MAINTAINER/.codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl/bin/codex",
        "exec", "--json", "--ignore-rules", "--color", "never",
        "-s", "workspace-write", "-C", str(workspace),
        "-m", "deepseek-flash",
        "--enable" if args.protocol == "v2" else "--disable", "multi_agent_v2",
        "--disable" if args.protocol == "v2" else "--enable", "multi_agent",
        "--disable", "code_mode", "--disable", "code_mode_host",
        "--disable", "code_mode_only",
        "-c", 'approval_policy="never"',
        "-c", f'projects.{json.dumps(str(workspace))}.trust_level="trusted"',
        args.prompt,
    ]
    env = {
        **os.environ,
        "CODEX_HOME": str(home),
        "HOME": str(home),
        "LANG": "C.UTF-8",
    }
    started = time.monotonic()
    with (base / "stdout.jsonl").open("wb") as stdout, (base / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL,
                                   env=env, start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
    events = []
    for line in (base / "stdout.jsonl").read_text(errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    collab = [
        event.get("item", {})
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "collab_tool_call"
    ]
    spawns = [item for item in collab if item.get("tool") == "spawn_agent"]
    child_ids = sorted({
        child for item in spawns for child in (item.get("receiver_thread_ids") or [])
    })
    turns = [event for event in events if event.get("type") == "turn.completed"]
    result = {
        "status": "NO_SPAWN" if not spawns else (
            "CHILD_OBSERVED" if child_ids else "SPAWN_NO_CHILD_ID"
        ),
        "protocol": args.protocol,
        "requested_provider": "deepseek",
        "requested_model": "deepseek-flash",
        "codex_cli": "0.163.0",
        "mcp_servers_configured": 0,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "thread_started": next((event.get("thread_id") for event in events
                                if event.get("type") == "thread.started"), None),
        "spawn_count": len(spawns),
        "child_ids": child_ids,
        "collab_tools": sorted({item.get("tool") for item in collab if item.get("tool")}),
        "spawn_events": spawns,
        "collab_event_count": len(collab),
        "turn_completed": bool(turns),
        "usage": turns[-1].get("usage") if turns else None,
        "config_sha256": hashlib.sha256((home / "config.toml").read_bytes()).hexdigest(),
        "stdout_sha256": hashlib.sha256((base / "stdout.jsonl").read_bytes()).hexdigest(),
        "stderr_sha256": hashlib.sha256((base / "stderr.log").read_bytes()).hexdigest(),
        "stderr_has_mcp_9000": "127.0.0.1:9000" in (base / "stderr.log").read_text(errors="replace"),
        "stderr_has_project_ignored": " is ignored" in (base / "stderr.log").read_text(errors="replace"),
    }
    write(base / "RESULT.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "CHILD_OBSERVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
