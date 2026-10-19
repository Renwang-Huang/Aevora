#!/usr/bin/env python3
"""Real isolated Codex CLI against a synthetic loopback Responses fixture.

No real model endpoint or identity file is used. The existing UDS broker,
namespace bridge, native command builder and resource boundary are reused.
The fixture only supplies public synthetic final text, not a benchmark repair.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
MODEL = "gpt-5.6-terra"
TEXT = "SYNTHETIC_RECOVERY_OK"
RUNTIME = Path(os.environ.get("ORDERFLOW_PYTHON_RUNTIME", sys.base_prefix))
BINARY = Path(os.environ.get("ORDERFLOW_CODEX_BINARY", shutil.which("codex") or "codex"))


def public_response(attempt: int, *, completed: bool) -> dict:
    message = {"id": f"msg_synthetic_{attempt}", "type": "message", "role": "assistant",
               "status": "completed", "channel": "final", "content": [
                   {"type": "output_text", "text": TEXT, "annotations": []}]}
    response = {"id": f"resp_synthetic_{attempt}", "object": "response",
                "status": "completed" if completed else "in_progress", "model": MODEL,
                "reasoning": {"effort": "max"}, "output": [message] if completed else []}
    if completed:
        response["usage"] = {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6,
                             "input_tokens_details": {"cached_tokens": 0},
                             "output_tokens_details": {"reasoning_tokens": 0}}
    return response


def sse(item: dict) -> bytes:
    return b"data: " + json.dumps(item).encode() + b"\n\n"


def successful_events(attempt: int) -> bytes:
    response = public_response(attempt, completed=True)
    return b"".join(sse(item) for item in (
        {"type": "response.created", "response": public_response(attempt, completed=False)},
        {"type": "response.output_item.done", "output_index": 0, "item": response["output"][0]},
        {"type": "response.completed", "response": response}))


class SyntheticUpstream:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.records = []
        self.lock = threading.Lock()
        self.response_attempts = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_):
                pass

            def do_GET(self):
                with owner.lock:
                    owner.records.append({"method": "GET", "path": self.path, "status": 200})
                body = b'{"models":[]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                assert body.get("model") == MODEL and body.get("reasoning", {}).get("effort") == "max"
                assert body.get("stream") is True
                with owner.lock:
                    owner.response_attempts += 1
                    attempt = owner.response_attempts
                    fault = owner.scenario.startswith("permanent") or attempt == 1
                    kind = "503" if owner.scenario.endswith("503") else "stream"
                    owner.records.append({"method": "POST", "path": self.path,
                                          "response_attempt": attempt,
                                          "model": body.get("model"), "effort": body.get("reasoning", {}).get("effort"),
                                          "status": 503 if fault and kind == "503" else 200,
                                          "fixture": "fault_" + kind if fault else "complete_sse"})
                if fault and kind == "503":
                    data = b'{"error":{"type":"synthetic_unavailable","message":"controlled local 503"}}'
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    data = (sse({"type": "response.created",
                                 "response": public_response(attempt, completed=False)})
                            if fault else successful_events(attempt))
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(data)
                    self.wfile.flush()
                    # Fault-stream deliberately closes with no response.completed.
                    self.close_connection = True

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def bootstrap(args: list[str]) -> int:
    """Mount only the public Python runtime, executable/helper and project."""
    runtime = Path(os.environ.get("ORDERFLOW_RETRY_PYTHON_RUNTIME", str(RUNTIME)))
    binary = Path(os.environ.get("ORDERFLOW_RETRY_CODEX_BINARY", str(BINARY)))
    command = ["/usr/bin/bwrap", "--die-with-parent", "--unshare-user", "--unshare-pid",
               "--ro-bind", str(runtime), "/usr", "--symlink", "usr/lib", "/lib",
               "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
               "--tmpfs", "/tmp", "--ro-bind", "/usr/bin/bwrap", "/tools/bwrap",
               "--ro-bind", "/usr/bin/git", "/tools/git",
               "--ro-bind", str(binary), "/tools/codex",
               "--ro-bind", str(binary.with_name("codex-code-mode-host")), "/tools/codex-code-mode-host",
               "--bind", "/sys/fs/cgroup", "/sys/fs/cgroup",
               "--bind", str(ROOT), str(ROOT), "--chdir", str(ROOT), "--clearenv",
               "--setenv", "HOME", "/tmp", "--setenv", "PATH", "/tools:/usr/bin",
               "--setenv", "ORDERFLOW_CGROUP_PARENT",
               "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.gnome.Terminal.slice",
               str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "--inside-runtime", *args]
    return subprocess.run(command).returncode


def probe(args) -> int:
    sys.path.insert(0, str(ROOT))
    from benchmark.participant_sandbox import participant_command
    from benchmark.resources import CgroupScope, PARTICIPANT_LIMITS, ResourceWatchdog
    from integrations.codex_agent import CodexConfig, native_command
    from integrations.codex_trace import redact_text
    from integrations.gateway_broker import SecureModelBroker
    from integrations.providers import ProviderConfig

    archive = args.archive.resolve()
    archive.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    binary = Path("/tools/codex")
    helper = binary.with_name("codex-code-mode-host")
    limits = replace(PARTICIPANT_LIMITS, wall_seconds=45.0)
    with tempfile.TemporaryDirectory(prefix="of-synthetic-retry-") as directory, SyntheticUpstream(args.scenario) as upstream:
        directory = Path(directory)
        workspace, state = directory / "workspace", directory / "state"
        workspace.mkdir()
        state.mkdir(mode=0o700)
        (workspace / "AGENTS.md").write_text("This is a public synthetic transport probe. No tools are required.\n")
        subprocess.run(["/tools/git", "init", "-q", str(workspace)], check=True)
        secret_path = directory / "synthetic.key"
        secret_path.write_text("synthetic-retry-upstream-key-not-a-live-credential")
        secret_path.chmod(0o600)
        token = secrets.token_urlsafe(32)
        config = CodexConfig(binary, secret_path, model=MODEL, provider_id="gateway", reasoning_effort="max",
                             timeout_seconds=limits.wall_seconds, request_budget=args.budget)
        version_command = participant_command(workspace, state, binary, ["/opt/codex/codex", "--version"],
                                              network_isolated=True, code_mode_host_binary=helper, resources=limits)
        version = subprocess.run(version_command, capture_output=True, text=True, timeout=15)
        if version.returncode or version.stdout.strip() != "codex-cli 0.162.1":
            raise RuntimeError("Expected real installed Codex CLI 0.162.1 in the participant boundary")
        (archive / "version.txt").write_text(version.stdout)
        broker = SecureModelBroker(ProviderConfig(), secret_path, run_id="synthetic-retry-" + archive.name,
            socket_path=directory / "broker.sock", run_token=token, request_budget=args.budget,
            max_concurrency=4, request_timeout=120,
            test_upstream_base_url=f"http://127.0.0.1:{upstream.server.server_port}/v1")
        scope = CgroupScope.create(limits)
        watchdog = None
        try:
            with broker:
                native = native_command(config, "http://127.0.0.1:9180/v1")
                if args.retries is not None:
                    for index, part in enumerate(native):
                        if part.startswith(("model_providers.orderflow_broker.request_max_retries=",
                                            "model_providers.orderflow_broker.stream_max_retries=")):
                            native[index] = part.split("=", 1)[0] + "=" + str(args.retries)
                native_overrides = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in native if "=" in part}
                inner = ["/usr/bin/python3.12", "-I", "-B", "/model_bridge.py", "--", *native]
                command = scope.wrap_command(participant_command(workspace, state, binary, inner,
                    broker_socket=broker.socket_path, network_isolated=True, code_mode_host_binary=helper, resources=limits))
                (archive / "command.json").write_text(json.dumps({"argv": command,
                    "source": "real installed CLI; synthetic loopback upstream only", "real_gateway_requests": 0,
                    "scenario": args.scenario, "override_retries_for_probe": args.retries,
                    "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2) + "\n")
                payload = json.dumps({"run_token": token}).encode() + b"\nReply with the public synthetic final text.\n"
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True)
                watchdog = ResourceWatchdog(process.pid, limits, output_roots=(workspace, state, archive)).start()
                try:
                    stdout, stderr = process.communicate(payload, timeout=limits.wall_seconds)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate(timeout=10)
                scrub = (*broker.secret_values, token)
                (archive / "codex_events.jsonl").write_text(redact_text(stdout.decode(errors="replace"), secret_values=scrub))
                (archive / "codex_stderr.log").write_text(redact_text(stderr.decode(errors="replace"), secret_values=scrub))
        finally:
            resource_watchdog = watchdog.close(cleanup=True) if watchdog else None
            resource_cgroup = scope.close()
        events = [json.loads(line) for line in (archive / "codex_events.jsonl").read_text().splitlines()]
        result = {"source": "real Codex CLI 0.162.1; synthetic upstream; not a real model task",
                  "real_gateway_requests": 0, "scenario": args.scenario, "cli_exit_code": process.returncode,
                  "turn_completed": any(event.get("type") == "turn.completed" for event in events),
                  "turn_failed": any(event.get("type") == "turn.failed" for event in events),
                  "public_final_text_observed": TEXT in (archive / "codex_events.jsonl").read_text(),
                  "response_attempts": upstream.response_attempts, "upstream_fixture_records": upstream.records,
                  "native_overrides": native_overrides, "broker": broker.metadata,
                  "elapsed_seconds": time.monotonic() - started,
                  "resource_watchdog": resource_watchdog, "resource_cgroup": resource_cgroup}
        (archive / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({key: result[key] for key in ("scenario", "cli_exit_code", "turn_completed",
              "turn_failed", "public_final_text_observed", "response_attempts", "elapsed_seconds")}))
        assert result["broker"]["upstream_requests"] == len(upstream.records)
        assert result["broker"]["upstream_requests"] <= args.budget
        assert resource_watchdog["violation"] is None and resource_cgroup["cleanup_complete"] is True
        retry_count = int(native_overrides["model_providers.orderflow_broker.request_max_retries"])
        stream_count = int(native_overrides["model_providers.orderflow_broker.stream_max_retries"])
        if args.budget == 2:
            assert process.returncode != 0 and upstream.response_attempts == 1
            assert result["broker"]["error_counts"].get("RUN_REQUEST_BUDGET_EXHAUSTED") == 1
        elif args.scenario == "permanent-503":
            assert process.returncode != 0 and upstream.response_attempts == (1 + retry_count) * (1 + stream_count)
        elif args.scenario == "permanent-stream":
            assert process.returncode != 0 and upstream.response_attempts == 1 + stream_count
        else:
            recoverable = retry_count > 0 if args.scenario.endswith("503") else stream_count > 0
            assert process.returncode == (0 if recoverable else 1)
            assert upstream.response_attempts == (2 if recoverable else 1)
        if process.returncode == 0:
            assert result["turn_completed"] and result["public_final_text_observed"]
        return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--scenario", choices=("transient-503", "transient-stream", "permanent-503", "permanent-stream"), required=True)
    parser.add_argument("--retries", type=int, choices=(0, 2), default=None, help="Explicit synthetic proof override; omitted uses native_command unchanged")
    parser.add_argument("--budget", type=int, default=160)
    parser.add_argument("--inside-runtime", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.inside_runtime:
        return bootstrap(sys.argv[1:])
    return probe(args)


if __name__ == "__main__":
    raise SystemExit(main())
