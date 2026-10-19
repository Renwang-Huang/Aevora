"""H2 real OS/official-SDK security contracts; no natural Agent run claim."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
import uuid

import pytest

from aevora.mcp_broker import MCPBroker
from scripts import aevora_h2_security as security
from test_gateway_broker import _broker, _request, _upstream, _wait_records


VALID_ENV = {"AEVORA_FALKORDB_HOST": "127.0.0.1", "AEVORA_FALKORDB_PORT": "17679",
             "AEVORA_FALKORDB_GRAPH": "aevora_h2_g0"}


def test_h2_graph_guard_accepts_only_explicit_dedicated_environment():
    assert security.require_h2_graph(VALID_ENV) == {
        "host": "127.0.0.1", "port": 17679, "graph": "aevora_h2_g0"}


@pytest.mark.parametrize("changes", [
    {"AEVORA_FALKORDB_PORT": "16379"}, {"AEVORA_FALKORDB_PORT": "1"},
    {"AEVORA_FALKORDB_HOST": "localhost"}, {"AEVORA_FALKORDB_HOST": "remote.example"},
    {"AEVORA_FALKORDB_GRAPH": "aevora_h1_release1"}, {"AEVORA_FALKORDB_GRAPH": ""},
    {"AEVORA_FALKORDB_PORT": "not-an-integer"},
])
def test_h2_graph_guard_refuses_before_database_connection(changes):
    with pytest.raises(ValueError):
        security.require_h2_graph({**VALID_ENV, **changes})


def test_h2_graph_guard_has_no_implicit_h1_defaults():
    with pytest.raises(ValueError):
        security.require_h2_graph({})


def test_evidence_is_exclusive_and_failure_stays_in_denominator(tmp_path):
    evidence = security.Evidence(tmp_path / "fresh")
    assert evidence.check("negative", False, {"actual_error": True}, scope="synthetic unit fixture") is False
    assert evidence.finish("unit") == 1
    result = json.loads((evidence.output / "summary.json").read_text())
    assert result["status"] == "FAIL" and result["overall_security"] == "PARTIAL"
    assert len(result["checks"]) == 1 and result["model_calls"] == 0
    with pytest.raises(FileExistsError):
        security.Evidence(evidence.output)


@pytest.mark.parametrize("field", ["active_connections", "active_sdk_children", "token_revoked",
                                 "socket_unlinked", "handler_cleanup_complete", "server_thread_stopped"])
def test_cleanup_requires_every_authority_and_process_condition(field):
    metadata = {"active_connections": 0, "active_sdk_children": 0, "token_revoked": True,
                "socket_unlinked": True, "handler_cleanup_complete": True, "server_thread_stopped": True}
    assert security.cleanup_pass(metadata)
    metadata[field] = 1 if field.startswith("active_") else False
    assert not security.cleanup_pass(metadata)


@pytest.fixture
def official_broker(tmp_path):
    """Default production SDK executable, no synthetic server or Resolver."""
    instances = []
    directories = []
    def create(**options):
        directory = tempfile.TemporaryDirectory(prefix="aevora-h2-unit-")
        directories.append(directory)
        token = secrets.token_urlsafe(32)
        # The unavailable password path proves graph errors are not success,
        # and prevents a contract test from ever reading a real credential.
        broker = MCPBroker(run_id="h2-unit-" + uuid.uuid4().hex,
            public_context={}, socket_path=Path(directory.name) / "mcp.sock",
            run_token=token, event_path=tmp_path / (uuid.uuid4().hex + ".jsonl"),
            server_environment={"AEVORA_FALKORDB_PASSWORD_FILE": "/missing-h2-synthetic-password-file"}, **options)
        broker.__enter__(); instances.append(broker)
        return broker, token
    yield create
    for broker in instances:
        broker.close()
        assert security.cleanup_pass(broker.metadata)
    for directory in directories:
        directory.cleanup()


@pytest.mark.parametrize("variant", ["wrong_token", "foreign_run", "wrong_peer_uid"])
def test_real_admission_denies_authority_before_official_sdk_start(official_broker, tmp_path, variant):
    options = {"allowed_peer_uid": os.getuid() + 1} if variant == "wrong_peer_uid" else {}
    broker, token = official_broker(**options)
    client = security.RPCClient(broker, "invalid_test_capability_0123456789" if variant == "wrong_token" else token,
        tmp_path / "client.jsonl", run_id="foreign-run" if variant == "foreign_run" else None)
    try:
        assert client.ack["aevora_transport"] == "REJECTED"
        assert broker.metadata["sdk_children_started"] == 0
    finally:
        client.close()
    assert token not in (tmp_path / "client.jsonl").read_text()


def test_default_official_sdk_graph_unavailable_is_error_with_no_fallback(official_broker, tmp_path):
    broker, token = official_broker()
    client = security.RPCClient(broker, token, tmp_path / "client.jsonl")
    try:
        assert client.ack == {"aevora_transport": "READY"}
        client.initialize()
        response = client.tool("resolve_experience", {"task_context": {}})
        assert response["result"]["isError"] is True
        assert "AEVORA_GRAPH_UNAVAILABLE" in json.dumps(response)
        assert "structuredContent" not in response["result"]
    finally:
        client.close()
    for line in (tmp_path / "client.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert hashlib.sha256(row["raw_json"].encode()).hexdigest() == row["sha256"]
    assert token not in (tmp_path / "client.jsonl").read_text()


@pytest.mark.parametrize("method,params,identifier,reason", [
    ("tools/call", {"name": "submit_outcome", "arguments": {"verdict": "PASS"}}, 2, "TOOL_NOT_ALLOWED"),
    ("tools/call", {"name": "cypher", "arguments": {"query": "MATCH(n) DETACH DELETE n"}}, 2, "TOOL_NOT_ALLOWED"),
    ("tools/call", {"name": "graph_admin", "arguments": {}}, 2, "TOOL_NOT_ALLOWED"),
    ("resources/read", {"uri": "file:///maintainer/aevora-db.password"}, 2, "METHOD_NOT_ALLOWED"),
    ("ping", {}, 1, "REQUEST_ID_REPLAY"),
])
def test_default_official_sdk_forbidden_requests_close_and_are_archived(
        official_broker, tmp_path, method, params, identifier, reason):
    broker, token = official_broker()
    client = security.RPCClient(broker, token, tmp_path / "client.jsonl")
    try:
        client.initialize()
        assert client.send({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}) is None
        deadline = time.monotonic() + 2
        while reason not in broker.metadata["rejections"] and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        assert broker.metadata["rejections"][reason] == 1
    finally:
        client.close()
    rows = [json.loads(line) for line in broker.event_path.read_text().splitlines()]
    assert any(row["category"] == "REJECTED" and row["reason"] == reason for row in rows)


def test_nonce_replay_rejected_after_actual_first_admission(official_broker, tmp_path):
    broker, token = official_broker()
    nonce = secrets.token_hex(32)
    first = security.RPCClient(broker, token, tmp_path / "first.jsonl", nonce=nonce)
    assert first.ack["aevora_transport"] == "READY"
    first.close()
    second = security.RPCClient(broker, token, tmp_path / "second.jsonl", nonce=nonce)
    try:
        assert second.ack["aevora_transport"] == "REJECTED"
        assert broker.metadata["accepted_connections"] == 1
    finally:
        second.close()


def test_owner_revocation_rejects_existing_and_new_actual_socket_clients(official_broker, tmp_path):
    broker, token = official_broker()
    client = security.RPCClient(broker, token, tmp_path / "client.jsonl")
    try:
        client.initialize()
        broker.close()
        assert client.call("ping") is None
        assert security.cleanup_pass(broker.metadata)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as retry:
            with pytest.raises(OSError):
                retry.connect(str(broker.socket_path))
        assert broker.metadata["token_lifetime"] == "BROKER_OWNER_LIFETIME"
    finally:
        client.close()


def test_gateway_admitted_then_actual_elapsed_expiry_rejects_without_upstream():
    """Real loopback HTTP/UDS and elapsed monotonic time; fake upstream only."""
    with _upstream() as upstream, _broker(upstream, token_ttl_seconds=1.0) as broker:
        assert _request(broker)[0] == 200
        admitted = _wait_records(broker)["upstream_requests"]
        remaining = broker._start_mono + broker.token_ttl_seconds - time.monotonic()
        if remaining > 0:
            threading.Event().wait(remaining + 0.02)
        status, _, body = _request(broker)
        assert status == 401
        assert json.loads(body)["error"]["type"] == "RUN_AUTHENTICATION_REQUIRED"
        assert _wait_records(broker, count=2)["upstream_requests"] == admitted == 1
        assert len(upstream["seen"]) == 1
    assert broker._token is None and not broker.socket_path.exists()


def test_runtime_contract_inventory_preserves_synthetic_boundary():
    assert "tests/test_completion_runtime.py" in security.RUNTIME_CONTRACTS
    assert "tests/test_gateway_broker.py" in security.RUNTIME_CONTRACTS
    assert "tests/test_codex_agent.py" in security.RUNTIME_CONTRACTS
    assert len(security.RUNTIME_CONTRACTS) == len(set(security.RUNTIME_CONTRACTS))
    assert all((security.ROOT / relative).is_file() for relative in security.RUNTIME_CONTRACTS)
