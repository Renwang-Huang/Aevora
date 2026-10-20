"""Strict end-to-end Witness pagination retest on a fresh closure Authority."""
from __future__ import annotations

import hashlib
import json
import copy
import os
from dataclasses import asdict
from pathlib import Path
import secrets
import socket
import sys
import tempfile

from audit import E, write
from aevora.mcp_broker import MCPBroker, PROTOCOL, MAX_MESSAGE_BYTES
from benchmark.manifest import load_manifest
from integrations.aevora import public_runtime_context
from integrations.aevora_v2 import prepare_runtime_configuration
from tools.experiments.g24.pagination_audit import reconstruct, verify_pages


BOOTSTRAP = E / "02_calibration/closure_world/CLOSURE_BOOTSTRAP.json"
TEST_WIRE_BUDGET = int(os.environ.get("G24_TEST_WIRE_BUDGET", "24576"))


def rpc(sock, reader, request_id, method, params, trace):
    request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    sock.sendall(json.dumps(request).encode() + b"\n")
    raw = reader.readline(MAX_MESSAGE_BYTES + 1)
    if not raw or len(raw) > MAX_MESSAGE_BYTES:
        raise RuntimeError("MCP response incomplete")
    response = json.loads(raw)
    trace.write(json.dumps({"request": request, "response": response,
                            "response_sha256": hashlib.sha256(raw).hexdigest()}) + "\n")
    trace.flush()
    return response


def collect_pages(sock, reader, trace, name, arguments, start_id):
    pages = []
    raw_responses = []
    cursor = None
    request_id = start_id
    while True:
        call_args = dict(arguments)
        if cursor:
            call_args["cursor"] = cursor
        response = rpc(sock, reader, request_id, "tools/call", {
            "name": name, "arguments": call_args,
        }, trace)
        raw_responses.append(response)
        result = response.get("result", {})
        if result.get("isError") is True:
            pages.append({"page": len(pages), "isError": True,
                          "error_text": result.get("content", [{}])[0].get("text", "")})
            return pages, raw_responses
        page = result.get("structuredContent")
        if not isinstance(page, dict):
            raise RuntimeError("MCP result lacks structuredContent")
        pages.append(page)
        if not page.get("has_more"):
            return pages, raw_responses
        cursor = page.get("next_cursor")
        if not cursor:
            raise RuntimeError("paged response lacks next_cursor")
        request_id += 1


def one_session(*, wire_budget: int, label: str) -> dict:
    manifest = load_manifest("SMOKE-001")
    context = public_runtime_context(asdict(manifest))
    run_id = "pagination-" + secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix="g24-pagination-") as directory:
        config, _, _ = prepare_runtime_configuration(BOOTSTRAP, run_id, context, directory)
        channel = Path(directory) / "channel"
        channel.mkdir(mode=0o700)
        broker_events = E / "09_evidence" / f"PAGINATION_BROKER_{label}_{run_id}.jsonl"
        client_trace = E / "09_evidence" / f"PAGINATION_CLIENT_{label}_{run_id}.jsonl"
        token = secrets.token_urlsafe(32)
        broker = MCPBroker(
            run_id=run_id,
            public_context=context,
            socket_path=channel / "mcp.sock",
            run_token=token,
            event_path=broker_events,
            enable_proposals=True,
            protocol_profile="aevora.mcp/2.0.0-rc2",
            v2_config_path=str(config),
            server_command=[sys.executable, "-I", "-B", str(E / "pagination_server.py")],
            server_environment={"G24_PAGINATION_WIRE_BUDGET": str(wire_budget)},
        )
        with broker:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect(str(broker.socket_path))
            reader = sock.makefile("rb")
            try:
                sock.sendall(json.dumps({
                    "protocol": PROTOCOL, "run_id": run_id,
                    "token": token, "nonce": secrets.token_hex(32),
                }).encode() + b"\n")
                ready = json.loads(reader.readline())
                if ready.get("aevora_transport") != "READY":
                    raise RuntimeError("broker not ready")
                with client_trace.open("x") as trace:
                    rpc(sock, reader, 1, "initialize", {
                        "protocolVersion": "2025-11-25", "capabilities": {},
                        "clientInfo": {"name": "G24 closure pagination", "version": "1"},
                    }, trace)
                    sock.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                    tools = rpc(sock, reader, 2, "tools/list", {}, trace)["result"]["tools"]
                    resolve = rpc(sock, reader, 3, "tools/call", {
                        "name": "resolve_experience", "arguments": {"task_context": {}},
                    }, trace)["result"]["structuredContent"]
                    candidate = resolve.get("recommendations", [])[0]
                    full = rpc(sock, reader, 10, "tools/call", {
                        "name": "build_evidence_bundle",
                        "arguments": {"experience_id": candidate["experience_id"],
                                      "query_id": resolve["query_id"]},
                    }, trace)["result"]["structuredContent"]
                    pages, raw_responses = collect_pages(
                        sock, reader, trace, "build_evidence_bundle",
                        {"experience_id": candidate["experience_id"],
                         "query_id": resolve["query_id"]},
                        20,
                    )
            finally:
                reader.close()
                sock.close()
        return {
            "label": label,
            "run_id": run_id,
            "wire_budget": wire_budget,
            "tools": sorted(item["name"] for item in tools),
            "query_id": resolve["query_id"],
            "experience_id": candidate["experience_id"],
            "full": full,
            "pages": pages,
            "raw_response_count": len(raw_responses),
            "client_trace": str(client_trace),
            "client_trace_sha256": hashlib.sha256(client_trace.read_bytes()).hexdigest(),
            "broker_events": str(broker_events),
            "broker_events_sha256": hashlib.sha256(broker_events.read_bytes()).hexdigest(),
            "broker_cleanup": {
                "active_connections": broker.metadata["active_connections"],
                "active_sdk_children": broker.metadata["active_sdk_children"],
                "token_revoked": broker.metadata["token_revoked"],
                "socket_unlinked": broker.metadata["socket_unlinked"],
            },
        }


def main() -> int:
    reference = one_session(wire_budget=196608, label="reference")
    paged = one_session(wire_budget=TEST_WIRE_BUDGET, label="paged")
    verification = None
    try:
        verification = verify_pages(
            paged["pages"],
            reference["full"],
            ignore_fields=("query_id", "read_scope", "recommendation_id"),
        )
    except Exception as error:
        verification = {
            "status": "FAIL",
            "error_type": type(error).__name__,
            "error": str(error),
        }
    negative = {}
    controls = {
        "error_page": [{"isError": True, "content": [{"text": "SYNTHETIC_ERROR"}]}],
        "tampered_page": copy.deepcopy(paged["pages"]),
        "reordered_pages": list(reversed(copy.deepcopy(paged["pages"]))),
        "duplicate_page": copy.deepcopy(paged["pages"]) + [copy.deepcopy(paged["pages"][0])],
        "sha_mismatch": copy.deepcopy(paged["pages"]),
    }
    for entry in controls["tampered_page"][0]["entries"]:
        if "value" in entry:
            entry["value"] = "TAMPERED"
            break
    else:
        raise RuntimeError("No value entry available for tamper control")
    controls["sha_mismatch"][0]["document_sha256"] = "0" * 64
    for name, pages in controls.items():
        try:
            verify_pages(pages, reference["full"],
                         ignore_fields=("query_id", "read_scope", "recommendation_id"))
            negative[name] = {"status": "UNEXPECTED_PASS"}
        except Exception as error:
            negative[name] = {
                "status": "EXPECTED_FAIL",
                "error_type": type(error).__name__,
                "error": str(error),
            }
    result = {
        "status": "PASS" if verification["status"] == "PASS" else "FAIL",
        "test_scope": "FRESH_CLOSURE_GRAPH_AND_FRESH_AUTHORITY",
        "production_wire_budget": 196608,
        "test_wire_budget": TEST_WIRE_BUDGET,
        "production_wire_budget_changed": False,
        "reference": {key: value for key, value in reference.items() if key != "full"},
        "paged": {key: value for key, value in paged.items() if key not in {"full", "pages"}},
        "page_count": len(paged["pages"]),
        "page_evidence": [
            {
                "page": index,
                "has_more": page.get("has_more"),
                "offset": page.get("offset"),
                "entries": len(page.get("entries", [])),
                "isError": page.get("isError", False),
                "status": page.get("status"),
            }
            for index, page in enumerate(paged["pages"])
        ],
        "verification": verification,
        "negative_controls": negative,
    }
    write(E / "09_evidence/PAGINATION_RESULT.json", result)
    write(E / "09_evidence/PAGINATION_CLOSURE_EVIDENCE.json", {
        "status": result["status"],
        "reference": reference,
        "paged": {key: value for key, value in paged.items() if key != "full"},
        "reconstructed": reconstruct(paged["pages"]),
        "paged_pages": paged["pages"],
        "verification": verification,
    })
    print(json.dumps({"status": result["status"], "pages": result["page_count"],
                      "verification": verification}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
