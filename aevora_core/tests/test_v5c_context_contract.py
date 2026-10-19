"""Public contract tests; wire cases use official MCP STDIO and real FalkorDB.

Type-only cases are local schema checks, not live model or Outcome claims.
"""
import asyncio
import json
import uuid

import pytest

from aevora.mcp_server import PublicContextClaims, validate_public_context_claims
from aevora.historical_import import ATOMIC_ID, LOCK_ID, public_context
from test_mcp_real_graph import real_graph, connect, tool, make_broker, rpc


@pytest.fixture
def proposal_graph(monkeypatch):
    from aevora.graph_repository import GraphRepository
    from aevora.models import LIFECYCLE_SCHEMA_VERSION
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", "aevora_v5c_contract_" + uuid.uuid4().hex)
    repo = GraphRepository.from_environment()
    repo.initialize(schema_version=LIFECYCLE_SCHEMA_VERSION)
    yield repo
    repo._graph.delete()
    repo.close()


@pytest.mark.parametrize("value", [{}, {"worker_count_known": True},
    {"worker_count_known": False}, {"worker_count_known": None},
    {"concurrency_scope": None}, {"concurrency_scope": "UNKNOWN"},
    {"observed_failure_mode": "inventory_ledger_inconsistency"}])
def test_valid_claims_preserve_types_and_omission(value):
    assert validate_public_context_claims(value) == value


@pytest.mark.parametrize("value", [{"worker_count_known": [2, 4]},
    {"worker_count_known": {"value": True}}, {"worker_count_known": 1},
    {"worker_count_known": 0}, {"worker_count_known": "true"},
    {"concurrency_scope": ["independent_processes"]},
    {"concurrency_scope": {"value": "independent_processes"}},
    {"concurrency_scope": 3}, {"task_id": "D"},
    {"read_only_observation": True}, {"verified": True}, []])
def test_invalid_claims_have_safe_field_error_without_values(value):
    with pytest.raises(ValueError, match="AEVORA_CONTEXT_SCHEMA_INVALID"):
        validate_public_context_claims(value)


def test_error_never_echoes_rejected_values_or_arbitrary_field_names():
    marker = "SENSITIVE_VALUE_NOT_TO_ECHO"
    with pytest.raises(ValueError) as caught:
        validate_public_context_claims({"worker_count_known": [marker], marker: marker})
    assert marker not in str(caught.value)
    assert "worker_count_known" in str(caught.value)
    assert "unsupported_field" in str(caught.value)


def test_schema_has_exact_eight_optional_scalar_facts():
    s = PublicContextClaims.model_json_schema()
    assert s["additionalProperties"] is False
    assert set(s["properties"]) == {"concurrency_scope", "worker_count_known",
        "shared_state_kind", "synchronization_scope", "transaction_guarantees",
        "observed_failure_mode", "shared_object_scope", "sqlite_journal_mode"}
    assert not s.get("required")
    for name, field in s["properties"].items():
        assert {v["type"] for v in field["anyOf"]} == ({"boolean", "null"} if name == "worker_count_known" else {"string", "null"})
        assert "enum" not in field  # No fabricated closed vocabulary.


@pytest.mark.parametrize("arguments", [
    {"task_context": {"worker_count_known": [2, 4]}},
    {"task_context": {"worker_count_known": 1}},
    {"task_context": {"shared_state_kind": {"value": "sqlite_file"}}},
    {"task_context": {"task_id": "D"}},
    {"task_context": {"read_only_observation": True}},
    {"task_context": "{}"}, {"task_context": {}, "verified": True}])
def test_real_wire_rejects_schema_violations_without_graph_write(real_graph, tmp_path, arguments):
    before = real_graph.state_fingerprint()
    broker, token = make_broker(tmp_path, "v5c-" + uuid.uuid4().hex)
    with broker:
        channel, reader = connect(broker, token)
        try:
            result = tool(channel, reader, 2, "resolve_experience", arguments)
            assert result["isError"] is True
            assert "AEVORA_CONTEXT_" in result["content"][0]["text"]
            assert real_graph.state_fingerprint() == before
        finally:
            reader.close(); channel.close()


def test_real_wire_discloses_same_schema_and_accepts_empty_and_exact_facts(real_graph, tmp_path):
    broker, token = make_broker(tmp_path, "v5c-" + uuid.uuid4().hex, enable_proposals=True)
    with broker:
        channel, reader = connect(broker, token)
        try:
            catalog = rpc(channel, reader, 2, "tools/list")
            assert {t["name"] for t in catalog["tools"]} == {
                "resolve_experience", "build_evidence_bundle", "record_decision", "propose_experience"}
            schema = next(t["inputSchema"] for t in catalog["tools"] if t["name"] == "resolve_experience")
            assert schema["additionalProperties"] is False
            disclosed = schema["properties"]["task_context"]
            actual = PublicContextClaims.model_json_schema()
            assert disclosed["properties"] == actual["properties"]
            assert disclosed["additionalProperties"] is False
            for i, claims in enumerate([{}, public_context("multi_process_shared_sqlite")], 3):
                result = tool(channel, reader, i, "resolve_experience", {"task_context": claims})
                assert result["isError"] is False
                assert result["structuredContent"]["context"] == broker.public_context
                assert result["structuredContent"]["participant_claims"] == claims
        finally:
            reader.close(); channel.close()


def test_real_wire_pinned_conflict_is_generic_and_creates_no_query(real_graph, tmp_path):
    before = real_graph.state_fingerprint()
    broker, token = make_broker(tmp_path, "v5c-" + uuid.uuid4().hex)
    with broker:
        channel, reader = connect(broker, token)
        try:
            result = tool(channel, reader, 2, "resolve_experience",
                          {"task_context": {"concurrency_scope": "caller-conflict-marker"}})
            assert result["isError"] is True
            text = result["content"][0]["text"]
            assert "AEVORA_CONTEXT_CONFLICT" in text
            assert "caller-conflict-marker" not in text and "independent_processes" not in text
            assert real_graph.state_fingerprint() == before
        finally:
            reader.close(); channel.close()


def test_real_wire_unknown_pins_cannot_be_promoted(real_graph, tmp_path):
    pinned = public_context(None)
    broker, token = make_broker(tmp_path, "v5c-" + uuid.uuid4().hex, public_context=pinned)
    with broker:
        channel, reader = connect(broker, token)
        try:
            result = tool(channel, reader, 2, "resolve_experience",
                          {"task_context": public_context("single_process_multi_thread")})
            assert result["isError"] is False
            v = result["structuredContent"]
            assert v["context"] == pinned
            assert {x["experience_id"]: x["decision"] for x in v["candidates"]} == {LOCK_ID: "VERIFY", ATOMIC_ID: "VERIFY"}
        finally:
            reader.close(); channel.close()


def test_real_wire_foreign_proposal_source_and_forged_outcome_are_denied(proposal_graph, tmp_path):
    real_graph = proposal_graph
    source, token = make_broker(tmp_path, "v5c-source-" + uuid.uuid4().hex, enable_proposals=True)
    with source:
        ch, reader = connect(source, token)
        try:
            result = tool(ch, reader, 2, "resolve_experience", {"task_context": {}})
            query = result["structuredContent"]
        finally:
            reader.close(); ch.close()
    dest, token = make_broker(tmp_path, "v5c-dest-" + uuid.uuid4().hex, enable_proposals=True)
    proposal = {"candidate_key": "foreign-probe", "title": "Untrusted negative control",
        "strategy": "This is a permission probe, not engineering evidence",
        "public_summary": "Foreign source must be refused",
        "necessary_conditions": {"shared_state_kind": ["sqlite_file"]},
        "inapplicable_conditions": {}, "scope": {"shared_state_kind": ["sqlite_file"]},
        "unknown_fields": [], "limitations": ["No actual engineering action"],
        "source_references": [{"kind": "Query", "id": query["query_id"]}]}
    with dest:
        ch, reader = connect(dest, token)
        try:
            own = tool(ch, reader, 2, "resolve_experience", {"task_context": {}})["structuredContent"]
            owned_body = {**proposal, "source_references": [{"kind": "Query", "id": own["query_id"]}]}
            accepted = tool(ch, reader, 3, "propose_experience", {"proposal": owned_body})
            assert accepted["isError"] is False
            assert accepted["structuredContent"]["status"] == "PROPOSED_UNTRUSTED"
            before = real_graph.state_fingerprint()
            rejected = tool(ch, reader, 4, "propose_experience", {"proposal": proposal})
            assert rejected["isError"] is True
            forged = tool(ch, reader, 5, "propose_experience", {"proposal": {**owned_body, "verified": True}})
            assert forged["isError"] is True
            assert real_graph.state_fingerprint() == before
        finally:
            reader.close(); ch.close()
