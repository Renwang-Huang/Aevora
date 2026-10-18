"""Participant stdio transport for one revocable Aevora Unix channel.

This file intentionally uses only the standard library. It is the only Aevora
source mounted inside the participant: it has no database client or host key.
The official MCP implementation runs on the trusted side of the socket.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import sys
import threading


MAX_MESSAGE_BYTES = 262_144
SOCKET_PATH = "/aevora-channel/mcp.sock"
PROTOCOL = "aevora-mcp-uds-v1"


def main() -> int:
    token = os.environ.pop("AEVORA_RUN_TOKEN", "")
    run_id = os.environ.get("AEVORA_RUN_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", run_id):
        sys.stderr.write("Aevora scoped MCP authority is unavailable.\n")
        return 1
    # This argument-free fixed path prevents the participant from repurposing
    # the proxy as a general socket or host-file forwarding interface.
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stopped = threading.Event()
    failure = []
    try:
        connection.settimeout(10)
        connection.connect(SOCKET_PATH)
        header = {"protocol": PROTOCOL, "run_id": run_id, "token": token,
                  "nonce": secrets.token_hex(32)}
        connection.sendall(json.dumps(header, separators=(",", ":")).encode() + b"\n")
        del header, token
        reader = connection.makefile("rb")
        acknowledgement = reader.readline(1025)
        if len(acknowledgement) > 1024 or not acknowledgement.endswith(b"\n") or json.loads(acknowledgement).get("aevora_transport") != "READY":
            raise RuntimeError("Scoped transport rejected")
        # No idle wall timeout: a healthy completion-aware Codex session may
        # wait a long time between MCP calls. Broker bounds each active request.
        connection.settimeout(None)

        def send_input() -> None:
            try:
                while not stopped.is_set():
                    raw = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
                    if not raw:
                        connection.shutdown(socket.SHUT_WR)
                        return
                    if len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                        raise ValueError("MCP input exceeds framed message bound")
                    connection.sendall(raw)
            except (OSError, ValueError):
                failure.append(True)
                stopped.set()
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        thread = threading.Thread(target=send_input, name="aevora-mcp-input", daemon=True)
        thread.start()
        while not stopped.is_set():
            raw = reader.readline(MAX_MESSAGE_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                raise ValueError("MCP response exceeds framed message bound")
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()
        stopped.set()
        reader.close()
        return 1 if failure else 0
    except (OSError, ValueError, RuntimeError, TypeError):
        # Neither rejected headers nor exception text (which may contain
        # credentials supplied by a caller) are printed to participant logs.
        sys.stderr.write("Aevora scoped MCP transport failed.\n")
        return 1
    finally:
        stopped.set()
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
