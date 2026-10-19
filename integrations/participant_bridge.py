"""Read-only loopback HTTP bridge to a single authorized Unix model channel.

Runs inside the private participant network namespace. It has no upstream key,
host network interface or proxy support. Native Codex performs orchestration.
The short-lived run token arrives on a private stdin pipe, never command args.
"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import subprocess
import sys
import threading
from urllib.parse import urlsplit


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float | None = 130):
        super().__init__("model-channel", timeout=timeout)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Bridge(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def forward(self):
        if urlsplit(self.path).path not in ("/v1/models", "/v1/responses") or self.command not in ("GET", "POST"):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 4_000_000:
                self.send_error(413)
                return
            connection = UnixConnection("/model-channel/broker.sock", timeout=getattr(self.server, "upstream_timeout", 130))
            headers = {key: self.headers[key] for key in ("Authorization", "Content-Type", "Accept") if key in self.headers}
            connection.request(self.command, self.path, body=self.rfile.read(size) if size else None, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() in ("content-type", "x-request-id", "retry-after"):
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            while data := response.read1(65536):
                self.wfile.write(data)
                self.wfile.flush()
        except (OSError, http.client.HTTPException, ValueError):
            self.close_connection = True
        finally:
            if "connection" in locals():
                connection.close()

    do_GET = forward
    do_POST = forward


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(130)
        return connection, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    header = json.loads(sys.stdin.buffer.readline(8192))
    token = header.get("run_token")
    if not isinstance(token, str) or len(token) < 32 or not command:
        raise RuntimeError("Invalid bounded model channel launch")
    prompt = sys.stdin.buffer.read(1_000_001)
    if len(prompt) > 1_000_000:
        raise RuntimeError("Public input too large")
    policy = header.get("completion_policy", "bounded")
    if policy not in ("bounded", "completion-aware"):
        raise RuntimeError("Invalid model transport policy")
    environment = dict(os.environ, ORDERFLOW_RUN_BROKER_TOKEN=token)
    if "aevora_run_token" in header or "aevora_run_id" in header:
        aevora_token, aevora_run_id = header.get("aevora_run_token"), header.get("aevora_run_id")
        if (not isinstance(aevora_token, str) or not 32 <= len(aevora_token) <= 256
                or not isinstance(aevora_run_id, str) or not 1 <= len(aevora_run_id) <= 128):
            raise RuntimeError("Invalid scoped Aevora launch authority")
        environment.update(AEVORA_RUN_TOKEN=aevora_token, AEVORA_RUN_ID=aevora_run_id)
    # Validate all private authority before opening a local listening socket.
    server = BoundedServer(("127.0.0.1", 9180), Bridge)
    # Local ingress remains bounded; upstream first response and SSE are not
    # capped by an inherited 130-second socket timeout in completion-aware mode.
    server.upstream_timeout = None if policy == "completion-aware" else 130
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, env=environment)
        process.communicate(prompt)
        return process.returncode
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
