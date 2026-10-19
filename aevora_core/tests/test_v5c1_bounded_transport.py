"""V5C.1 wire capacity and scope contracts.

Pure serialization/capability cases are explicitly synthetic; the graph cases
use actual isolated FalkorDB and official SDK/UDS. Neither is an Agent outcome.
"""
import copy
import json
import secrets
import tempfile
import uuid
from pathlib import Path

import pytest

from aevora.mcp_projection import PublicProjection, candidate_summary, fits, wire_bytes, _entries
from aevora.mcp_projection import WIRE_BUDGET, ProjectionCapacityError
from aevora.mcp_broker import MCPBroker, MAX_MESSAGE_BYTES, _message
from aevora.mcp_server import ExperienceService, validate_public_context_claims
from aevora.models import digest
from scripts.aevora_h2_security import RPCClient
from test_h2_governance import repo, attach, CTX, EXP


def reconstruct(entries):
    root = None
    for row in entries:
        parts = [s.replace("~1", "/").replace("~0", "~") for s in row["pointer"].split("/")[1:]]
        value = ({} if row.get("container") == "object" else
                 [None] * row["length"] if row.get("container") == "array" else row.get("value"))
        if not parts:
            if "string_offset" in row:
                assert row["string_offset"] == len(root or "")
                root = (root or "") + value
            else:
                root = value
            continue
        parent = root
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
        if "string_offset" in row:
            old = parent[key] if isinstance(parent, list) else parent.get(key)
            assert row["string_offset"] == len(old or "")
            value = (old or "") + value
        parent[key] = value
    return root


@pytest.mark.parametrize("value", [
    {"a/b~c": "汉😀\n\"\\" * 3000, "empty": [], "object": {}, "null": None},
    [{"position": i, "nested": [True, False, None]} for i in range(800)],
    "😀" * 12000, {"deep": {"one": {"two": ["x" * 6000]}}},
])
def test_lossless_rfc6901_roundtrip_multibyte_escaping_empty_and_large(value):
    assert reconstruct(list(_entries(value))) == value


class SyntheticBundle:
    """Serialization-only authority stub; no engineering verdict is supplied."""
    def __init__(self):
        self.document = {"experience_id": "experience:synthetic", "status": "SYNTHETIC_SERIALIZATION_ONLY",
                         "unfavorable_counterexamples": ["汉😀\n\"\\" * 400 for _ in range(30)]}
        self.reads = 0

    def build_evidence_bundle(self, experience_id, query_id=None):
        self.reads += 1
        return copy.deepcopy(self.document)


def pages(projector, first, experience_id="experience:synthetic", query_id=None, view="bundle"):
    values = [first]
    while values[-1]["has_more"]:
        assert len(values) < 128
        values.append(projector.bundle(experience_id, query_id, values[-1]["next_cursor"], view))
    return values


def test_complete_paginated_authorized_document_hash_and_every_wire_budget():
    source = SyntheticBundle(); projector = PublicProjection(source)
    result = pages(projector, projector.bundle("experience:synthetic"))
    assert len(result) > 1
    entries = [row for page in result for row in page["entries"]]
    restored = reconstruct(entries)
    assert restored == source.document and digest(restored) == result[0]["document_sha256"]
    assert all(fits(page) and len(wire_bytes(page)) < WIRE_BUDGET < MAX_MESSAGE_BYTES for page in result)
    assert source.reads > len(result)  # first read plus actual authorization on each page
    assert all(p["truncated"] and p["projection"] == "LOSSLESS_JSON_POINTER_ENTRIES" for p in result)


@pytest.mark.parametrize("attack", ["modified", "cross_connection", "cross_experience", "cross_query", "cross_view", "expired", "oversized", "malformed"])
def test_cursor_forgery_scope_expiry_and_bounded_errors(attack):
    clock = [0.0]; projector = PublicProjection(SyntheticBundle(), clock=lambda: clock[0])
    first = projector.bundle("experience:synthetic"); token = first["next_cursor"]
    assert token
    eid, qid, view = "experience:synthetic", None, "bundle"
    if attack == "modified": token = ("A" if token[0] != "A" else "B") + token[1:]
    if attack == "cross_connection": projector = PublicProjection(SyntheticBundle())
    if attack == "cross_experience": eid = "experience:foreign"
    if attack == "cross_query": qid = "query:foreign"
    if attack == "cross_view": view = "candidate"
    if attack == "expired": clock[0] = 901.0
    if attack == "oversized": token = "x" * 257
    if attack == "malformed": token = "!not-base64!"
    with pytest.raises(ValueError):
        projector.bundle(eid, qid, token, view)


def test_cursor_replay_is_idempotent_without_extending_expiry():
    projector = PublicProjection(SyntheticBundle()); first = projector.bundle("experience:synthetic")
    a = projector.bundle("experience:synthetic", cursor=first["next_cursor"])
    b = projector.bundle("experience:synthetic", cursor=first["next_cursor"])
    assert a == b


@pytest.mark.parametrize("size", [MAX_MESSAGE_BYTES - 1, MAX_MESSAGE_BYTES, MAX_MESSAGE_BYTES + 1])
def test_exact_existing_transport_byte_boundary(size):
    prefix = b'{"padding":"'; suffix = b'"}\n'
    raw = prefix + b'x' * (size - len(prefix) - len(suffix)) + suffix
    assert len(raw) == size
    if size <= MAX_MESSAGE_BYTES:
        assert _message(raw)["padding"]
    else:
        with pytest.raises(ValueError): _message(raw)


@pytest.mark.parametrize("claim", [{"observed_failure_mode": "汉" * 4000},
                                  {"observed_failure_mode": "\ud800"},
                                  {"observed_failure_mode": {"nested": "private-marker"}}])
def test_abusive_context_fails_without_echoing_input(claim):
    with pytest.raises(ValueError) as error:
        validate_public_context_claims(claim)
    assert "private-marker" not in str(error.value) and "汉" not in str(error.value)


def test_snapshot_cache_eviction_is_explicit_not_fallback(monkeypatch):
    import aevora.mcp_projection as module
    monkeypatch.setattr(module, "MAX_DOCUMENTS", 1)
    projector = PublicProjection(SyntheticBundle())
    first = projector.bundle("experience:synthetic")
    projector.bundle("experience:synthetic")
    with pytest.raises(ValueError):
        projector.bundle("experience:synthetic", cursor=first["next_cursor"])


def test_document_capacity_error_is_explicit(monkeypatch):
    import aevora.mcp_projection as module
    monkeypatch.setattr(module, "MAX_DOCUMENT_BYTES", 100)
    with pytest.raises(ProjectionCapacityError): PublicProjection(SyntheticBundle()).bundle("experience:synthetic")


@pytest.mark.parametrize("extra", [0, 2, 6])
def test_real_graph_sdk_growth_preserves_when_why_and_full_counterevidence(repo, extra, tmp_path):
    for index in range(extra):
        attach(repo, "capacity-" + str(index), "PASS" if index % 2 == 0 else "FAIL",
               text="Explicit synthetic graph capacity fixture " + "汉😀\n\"" * 80)
    source = ExperienceService(run_id="v5c1-real-" + uuid.uuid4().hex, public_context=CTX, repository=repo)
    expected = source.resolve_experience({})["candidates"][0]
    with tempfile.TemporaryDirectory(prefix="v5c1-wire-") as folder:
        token = secrets.token_hex(32)
        broker = MCPBroker(run_id=source.run_id, public_context=CTX,
            socket_path=Path(folder)/"mcp.sock", run_token=token, event_path=tmp_path/"mcp.jsonl")
        with broker:
            client = RPCClient(broker, token, tmp_path/"client.jsonl"); client.initialize()
            try:
                answer = client.tool("resolve_experience", {"task_context": {}})
                assert answer and answer["result"]["isError"] is False
                query = answer["result"]["structuredContent"]
                actual = query["candidates"][0]
                for key in ("experience_id", "decision", "reason", "retrieval_snapshot_sha256", "governance_evidence_sha256"):
                    assert actual[key] == expected[key]
                assert actual["evidence_index"]["relevant_counterexample_paths"]["count"] == len(expected["relevant_counterexample_paths"])
                detail = client.tool("build_evidence_bundle", {"experience_id": EXP, "query_id": query["query_id"], "view": "candidate"})
                assert detail and detail["result"]["isError"] is False
                page = detail["result"]["structuredContent"]; collected = []
                if page.get("projection") == "LOSSLESS_JSON_POINTER_ENTRIES":
                    document_sha = page["document_sha256"]
                    while True:
                        collected += page["entries"]
                        if not page["has_more"]: break
                        reply = client.tool("build_evidence_bundle", {"experience_id": EXP, "query_id": query["query_id"], "view": "candidate", "cursor": page["next_cursor"]})
                        assert reply and not reply["result"]["isError"]
                        page = reply["result"]["structuredContent"]
                    complete = reconstruct(collected)
                    assert digest(complete) == document_sha
                else:
                    complete = page
                assert complete["decision"] == expected["decision"]
                assert complete["relevant_counterexample_paths"] == expected["relevant_counterexample_paths"]
                assert complete["evidence_bundle"]["paths"] == expected["evidence_bundle"]["paths"]
            finally: client.close()
        assert broker.metadata["handler_cleanup_complete"] is True


def test_preview_is_explicit_and_never_changes_decision_or_reference(repo):
    service = ExperienceService(run_id="v5c1-preview", public_context=CTX, repository=repo)
    full = service.resolve_experience({}); raw = full["candidates"][0]
    row = candidate_summary(raw, full["query_id"])
    assert row["decision"] == raw["decision"] and row["truncated"] is True
    assert row["detail_reference"]["query_id"] == full["query_id"]
    assert row["full_candidate_sha256"] == digest(raw)
    assert "evidence_bundle" not in row and row["evidence_index"]


def test_index_cache_does_not_retain_full_unbudgeted_resolver_document(repo):
    service = ExperienceService(run_id="v5c1-cache-bound", public_context=CTX, repository=repo)
    projection = PublicProjection(service)
    projection.resolve({})
    for document in projection._documents.values():
        captured = [cell.cell_contents for cell in document["authorize"].__closure__]
        assert not any(isinstance(value, dict) and "candidates" in value for value in captured)
    from aevora.mcp_server import PublicContextClaims
    assert "8192" in PublicContextClaims.model_json_schema()["description"]


def test_real_graph_long_candidate_pages_refuse_removed_authorization_and_foreign_connection(repo, tmp_path):
    attach(repo, "large-public-evidence", text="Explicit synthetic capacity evidence: " + "x" * 24000)
    run_id = "v5c1-authorization-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="v5c1-authority-") as folder:
        token = secrets.token_hex(32)
        broker = MCPBroker(run_id=run_id, public_context=CTX, socket_path=Path(folder)/"mcp.sock",
                           run_token=token, event_path=tmp_path/"authority_mcp.jsonl")
        with broker:
            client = RPCClient(broker, token, tmp_path/"authority_client.jsonl"); client.initialize()
            foreign = RPCClient(broker, token, tmp_path/"other_connection.jsonl"); foreign.initialize()
            try:
                q = client.tool("resolve_experience", {"task_context": {}})["result"]["structuredContent"]
                args = {"experience_id": EXP, "query_id": q["query_id"], "view": "candidate"}
                first = client.tool("build_evidence_bundle", args)["result"]["structuredContent"]
                assert first["has_more"] and first["projection"] == "LOSSLESS_JSON_POINTER_ENTRIES"
                cursor_args = {**args, "cursor": first["next_cursor"]}
                wrong = foreign.tool("build_evidence_bundle", cursor_args)
                assert wrong["result"]["isError"] is True
                edge = repo.query("MATCH(:Query {id:$q})-[r:CONSIDERED]->(:Experience {id:$e}) RETURN r.payload_json",
                                  {"q": q["query_id"], "e": EXP})[0][0]
                try:
                    repo.query("MATCH(:Query {id:$q})-[r:CONSIDERED]->(:Experience {id:$e}) DELETE r",
                               {"q": q["query_id"], "e": EXP}, read_only=False)
                    denied = client.tool("build_evidence_bundle", cursor_args)
                    assert denied["result"]["isError"] is True
                finally:
                    repo.put_edge("CONSIDERED", "Query", q["query_id"], "Experience", EXP, json.loads(edge))
                restored = client.tool("build_evidence_bundle", cursor_args)
                assert restored["result"]["isError"] is False
            finally:
                client.close(); foreign.close()


def test_real_graph_candidate_index_paginates_without_dropping_competitors(repo, tmp_path):
    for index in range(24):
        suffix = "v5c1-index-" + str(index)
        repo.import_experience({"id": "experience:" + suffix, "strategy": "Synthetic capacity contract",
            "title": "Synthetic index competitor " + str(index), "source_type": "synthetic_or_test_fixture",
            "public_summary": "No engineering outcome is asserted by this test", "created_at": "2026-10-15T00:00:00+00:00"},
            {"id": "rule:" + suffix, "version": "synthetic/1", "premises": [
                {"id": "premise:" + suffix, "fact_key": "worker_count_known", "allowed_values": [True]}]})
    expected = set(repo.experience_ids())
    with tempfile.TemporaryDirectory(prefix="v5c1-index-") as folder:
        token = secrets.token_hex(32)
        with MCPBroker(run_id="v5c1-index-" + uuid.uuid4().hex, public_context=CTX,
                       socket_path=Path(folder)/"mcp.sock", run_token=token, event_path=tmp_path/"index_mcp.jsonl") as broker:
            client = RPCClient(broker, token, tmp_path/"index_client.jsonl"); client.initialize()
            try:
                result = client.tool("resolve_experience", {"task_context": {}})["result"]["structuredContent"]
                assert result["has_more"] and result["candidate_count"] == len(expected)
                found = []
                while True:
                    found += [row["experience_id"] for row in result["candidates"]]
                    if not result["has_more"]: break
                    reply = client.tool("resolve_experience", {"task_context": {}, "cursor": result["next_cursor"]})
                    assert reply["result"]["isError"] is False
                    result = reply["result"]["structuredContent"]
                assert found == sorted(expected) and len(found) == len(set(found))
            finally: client.close()
