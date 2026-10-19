"""Mandatory explicit G3 tests: official MCP SDK with copied real FalkorDB.

Run with scripts/aevora-python after the G1/G2 deployment gates. No fake graph
or resolver is selected. Only this test's UUID-named graph is removed.
"""
from __future__ import annotations

import json
import secrets
import socket
import uuid

import pytest

from aevora.graph_repository import GraphRepository
from aevora.historical_import import ATOMIC_ID, LOCK_ID, public_context
from aevora.mcp_broker import MCPBroker, PROTOCOL


@pytest.fixture
def real_graph(monkeypatch):
    main = GraphRepository.from_environment()
    assert main.get_node("Experience", ATOMIC_ID) is not None, "G1 history import must precede G3"
    graph_name = "aevora_test_mcp_" + uuid.uuid4().hex
    main._graph.copy(graph_name)
    main.close()
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", graph_name)
    copied = GraphRepository.from_environment()
    yield copied
    copied._graph.delete()
    copied.close()


def rpc(channel, reader, identifier, method, params=None):
    value = {"jsonrpc": "2.0", "id": identifier, "method": method}
    if params is not None:
        value["params"] = params
    channel.sendall(json.dumps(value).encode() + b"\n")
    result = json.loads(reader.readline())
    assert result["id"] == identifier
    return result["result"]


def connect(broker, token):
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    channel.settimeout(10)
    channel.connect(str(broker.socket_path))
    reader = channel.makefile("rb")
    channel.sendall(json.dumps({"protocol": PROTOCOL, "run_id": broker.run_id, "token": token,
                                "nonce": secrets.token_hex(32)}).encode() + b"\n")
    assert json.loads(reader.readline())["aevora_transport"] == "READY"
    initial = rpc(channel, reader, 1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                                    "clientInfo": {"name": "Aevora real graph SDK test", "version": "1"}})
    assert initial["serverInfo"]["name"] == "Aevora"
    channel.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    return channel, reader


def tool(channel, reader, identifier, name, arguments):
    return rpc(channel, reader, identifier, "tools/call", {"name": name, "arguments": arguments})


def make_broker(tmp_path, run_id, **options):
    folder = tmp_path / uuid.uuid4().hex
    folder.mkdir(mode=0o700)
    token = secrets.token_hex(32)
    pinned_context = options.pop("public_context", public_context("multi_process_shared_sqlite"))
    return MCPBroker(run_id=run_id, public_context=pinned_context,
                     socket_path=folder / "mcp.sock", run_token=token,
                     event_path=folder / "mcp_events.jsonl", **options), token


def test_unknown_topology_cannot_be_promoted_by_untrusted_participant_claim(real_graph, tmp_path):
    pinned = public_context(None)
    participant_claim = public_context("single_process_multi_thread")
    broker, token = make_broker(tmp_path, "run-" + uuid.uuid4().hex, public_context=pinned)
    with broker:
        channel, reader = connect(broker, token)
        try:
            result = tool(channel, reader, 2, "resolve_experience", {"task_context": participant_claim})
            assert result["isError"] is False
            response = result["structuredContent"]
            kinds = {row["experience_id"]: row["decision"] for row in response["candidates"]}
            assert kinds[LOCK_ID] == "VERIFY" and kinds[ATOMIC_ID] == "VERIFY"
            assert response["context"] == pinned and response["pinned_public_context"] == pinned
            assert response["participant_claims"] == participant_claim
            assert response["participant_claims_status"] == "UNVERIFIED_NOT_USED_FOR_APPLICABILITY"
            assert response["context_authority"] == "TRUSTED_PINNED_PUBLIC_FACTS_ONLY"
            query = real_graph.get_node("Query", response["query_id"])
            assert query["task_context"] == pinned and query["participant_claims"] == participant_claim
            assert query["task_context"]["concurrency_scope"] is None
        finally:
            reader.close(); channel.close()


def test_sdk_tools_really_query_graph_and_append_only_untrusted_decision(real_graph, tmp_path):
    run_id = "run-" + uuid.uuid4().hex
    broker, token = make_broker(tmp_path, run_id)
    before_outcomes = len(real_graph.query("MATCH(n:VerifiedOutcome) RETURN n.id"))
    with broker:
        channel, reader = connect(broker, token)
        try:
            query_result = tool(channel, reader, 2, "resolve_experience", {"task_context": {}})
            assert not query_result["isError"]
            query = query_result["structuredContent"]
            decisions = {row["experience_id"]: row["decision"] for row in query["candidates"]}
            assert decisions[ATOMIC_ID] == "APPLY" and decisions[LOCK_ID] == "ABSTAIN"
            assert real_graph.get_node("Query", query["query_id"])["run_id"] == run_id
            bundle = tool(channel, reader, 3, "build_evidence_bundle", {"experience_id": ATOMIC_ID})
            assert not bundle["isError"]
            assert bundle["structuredContent"]["support_paths"]
            for forbidden in ("private_verification", "source_reference", "hidden_tests/", "reference_patches/", "private_manifests/"):
                assert forbidden not in json.dumps(bundle)
            decision = {"decision_id": "decision:" + run_id + ":test", "query_id": query["query_id"],
                        "experience_id": ATOMIC_ID, "decision": "VERIFY", "reason": "Verify actual candidate behavior",
                        "verification_steps": ["Run public tests and inspect transaction unit of work"]}
            first = tool(channel, reader, 4, "record_decision", {"decision": decision})
            assert not first["isError"]
            receipt = first["structuredContent"]
            assert receipt["status"] == "RECORDED_UNTRUSTED" and receipt["attribution"] == "UNKNOWN"
            assert real_graph.get_node("Decision", receipt["decision_id"])["adoption"] == "CLAIM_ONLY"
            assert tool(channel, reader, 5, "record_decision", {"decision": decision})["structuredContent"] == receipt
            conflict = tool(channel, reader, 6, "record_decision", {"decision": {**decision, "reason": "Conflicting immutable bytes"}})
            assert conflict["isError"] is True
            assert real_graph.query("MATCH(n:AuditEvent) RETURN n.id")
            forbidden = tool(channel, reader, 7, "record_decision", {"decision": {**decision, "verdict": "PASS"}})
            assert forbidden["isError"] is True
            assert len(real_graph.query("MATCH(n:VerifiedOutcome) RETURN n.id")) == before_outcomes
        finally:
            reader.close(); channel.close()
    assert broker.metadata["handler_cleanup_complete"]
    assert token not in broker.event_path.read_text()


def test_same_run_connections_share_query_but_foreign_run_cannot_adopt(real_graph, tmp_path):
    run_id = "run-" + uuid.uuid4().hex
    broker, token = make_broker(tmp_path, run_id)
    with broker:
        first, first_reader = connect(broker, token)
        query = tool(first, first_reader, 2, "resolve_experience", {"task_context": {}})["structuredContent"]
        second, second_reader = connect(broker, token)
        try:
            assert not tool(second, second_reader, 2, "build_evidence_bundle", {"experience_id": ATOMIC_ID})["isError"]
            claim = {"query_id": query["query_id"], "experience_id": ATOMIC_ID, "decision": "ABSTAIN",
                     "reason": "A real claim is not causal attribution"}
            assert not tool(second, second_reader, 3, "record_decision", {"decision": claim})["isError"]
        finally:
            first_reader.close(); first.close(); second_reader.close(); second.close()
    other, other_token = make_broker(tmp_path, "run-" + uuid.uuid4().hex)
    with other:
        channel, reader = connect(other, other_token)
        try:
            assert tool(channel, reader, 2, "record_decision", {"decision": claim})["isError"] is True
            assert tool(channel, reader, 3, "build_evidence_bundle", {"experience_id": ATOMIC_ID})["isError"] is True
        finally:
            reader.close(); channel.close()


def test_actual_disconnected_database_yields_mcp_error_without_fallback(real_graph, tmp_path):
    broker, token = make_broker(tmp_path, "run-" + uuid.uuid4().hex,
                                server_environment={"AEVORA_FALKORDB_PORT": "1"})
    before = len(real_graph.query("MATCH(n:Query) RETURN n.id"))
    with broker:
        channel, reader = connect(broker, token)
        try:
            result = tool(channel, reader, 2, "resolve_experience", {"task_context": {}})
            assert result["isError"] is True
            assert "AEVORA_GRAPH_UNAVAILABLE" in json.dumps(result)
            assert "structuredContent" not in result
        finally:
            reader.close(); channel.close()
    assert len(real_graph.query("MATCH(n:Query) RETURN n.id")) == before
