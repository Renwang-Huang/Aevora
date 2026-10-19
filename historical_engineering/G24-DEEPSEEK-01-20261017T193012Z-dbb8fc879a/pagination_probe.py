"""Exercise the real v2 MCP projection pages through an authenticated broker."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import secrets
import socket
import sys
import tempfile

from audit import E, write
from aevora.mcp_broker import MCPBroker, PROTOCOL, MAX_MESSAGE_BYTES
from benchmark.manifest import load_manifest
from dataclasses import asdict
from integrations.aevora import public_runtime_context
from integrations.aevora_v2 import prepare_runtime_configuration


BOOTSTRAP = E / "02_calibration/smoke_world_v2/SMOKE_BOOTSTRAP.json"
WIRE_BUDGET = 12000


def rpc(sock, reader, identifier, method, params, event_stream):
    request = {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}
    sock.sendall(json.dumps(request).encode() + b"\n")
    raw = reader.readline(MAX_MESSAGE_BYTES + 1)
    if not raw or len(raw) > MAX_MESSAGE_BYTES:
        raise RuntimeError("MCP_RESPONSE_INVALID")
    event_stream.write(json.dumps({
        "request": request,
        "response": json.loads(raw),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
    }) + "\n")
    event_stream.flush()
    return json.loads(raw)["result"]


def follow_tool(sock, reader, start_id, name, arguments, event_stream):
    pages = []
    cursor = None
    identifier = start_id
    while True:
        payload = dict(arguments)
        if cursor:
            payload["cursor"] = cursor
        result = rpc(sock, reader, identifier, "tools/call", {
            "name": name,
            "arguments": payload,
        }, event_stream)
        value = result.get("structuredContent", result)
        pages.append({
            "page": len(pages),
            "status": value.get("status"),
            "has_more": value.get("has_more"),
            "next_cursor": value.get("next_cursor"),
            "projection": value.get("projection"),
            "document_sha256": value.get("document_sha256"),
            "keys": sorted(value),
        })
        if not value.get("has_more"):
            return pages, value
        cursor = value.get("next_cursor")
        if not cursor:
            raise RuntimeError("MISSING_NEXT_CURSOR")
        identifier += 1


def main() -> int:
    manifest = load_manifest("SMOKE-001")
    context = public_runtime_context(asdict(manifest))
    run_id = "pagination-" + secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix="g24-pg-") as directory:
        config, _, _ = prepare_runtime_configuration(
            BOOTSTRAP,
            run_id,
            context,
            directory,
        )
        channel = Path(directory) / "channel"
        channel.mkdir(mode=0o700)
        token = secrets.token_urlsafe(32)
        event_path = E / "09_evidence" / ("PAGINATION_MCP_TRACE-" + secrets.token_hex(8) + ".jsonl")
        broker = MCPBroker(
            run_id=run_id,
            public_context=context,
            socket_path=channel / "mcp.sock",
            run_token=token,
            event_path=event_path,
            enable_proposals=True,
            protocol_profile="aevora.mcp/2.0.0-rc2",
            v2_config_path=str(config),
            server_command=[
                sys.executable,
                "-I",
                "-B",
                str(E / "pagination_server.py"),
            ],
            server_environment={"G24_PAGINATION_WIRE_BUDGET": str(WIRE_BUDGET)},
        )
        with broker:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect(str(broker.socket_path))
            reader = sock.makefile("rb")
            try:
                sock.sendall(json.dumps({
                    "protocol": PROTOCOL,
                    "run_id": run_id,
                    "token": token,
                    "nonce": secrets.token_hex(32),
                }).encode() + b"\n")
                ready = json.loads(reader.readline())
                if ready.get("aevora_transport") != "READY":
                    raise RuntimeError("BROKER_NOT_READY")
                with event_path.open("w") as event_stream:
                    rpc(sock, reader, 1, "initialize", {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "G24 pagination probe", "version": "1"},
                    }, event_stream)
                    sock.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                    tools = rpc(sock, reader, 2, "tools/list", {}, event_stream)
                    resolve_pages, resolve_value = follow_tool(
                        sock, reader, 3, "resolve_experience",
                        {"task_context": {}}, event_stream,
                    )
                    candidates = resolve_value.get("candidates") or resolve_value.get("recommendations") or []
                    if not candidates:
                        raise RuntimeError("NO_CANDIDATE_FOR_PAGINATION")
                    experience_id = candidates[0].get("experience_id")
                    query_id = resolve_value.get("query_id")
                    bundle_pages, bundle_value = follow_tool(
                        sock, reader, 10, "build_evidence_bundle",
                        {"experience_id": experience_id, "query_id": query_id},
                        event_stream,
                    )
            finally:
                reader.close()
                sock.close()
        summary = {
            "status": "PASS",
            "scope": f"REAL_V2_MCP_PROJECTION_WITH_TEST_WIRE_BUDGET_{WIRE_BUDGET}",
            "production_wire_budget_changed": False,
            "tools": sorted(item["name"] for item in tools["tools"]),
            "resolve_pages": len(resolve_pages),
            "bundle_pages": len(bundle_pages),
            "resolve_page_evidence": resolve_pages,
            "bundle_page_evidence": bundle_pages,
            "resolve_experience_id": experience_id,
            "query_id": query_id,
            "bundle_status": bundle_value.get("status"),
            "trace": str(event_path),
            "trace_sha256": hashlib.sha256(event_path.read_bytes()).hexdigest(),
            "broker_cleanup": {
                "active_connections": broker.metadata["active_connections"],
                "active_sdk_children": broker.metadata["active_sdk_children"],
                "token_revoked": broker.metadata["token_revoked"],
                "socket_unlinked": broker.metadata["socket_unlinked"],
            },
        }
        write(E / "09_evidence/PAGINATION_RESULT.json", summary)
        print(json.dumps({
            "status": summary["status"],
            "resolve_pages": summary["resolve_pages"],
            "bundle_pages": summary["bundle_pages"],
        }, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
