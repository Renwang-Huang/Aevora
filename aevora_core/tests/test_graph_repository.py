"""G1 tests require and operate a real authenticated FalkorDB, never a fake backend."""
from __future__ import annotations

import os
import uuid

import pytest

from aevora.graph_repository import GraphRepository
from aevora.models import (GraphUnavailable, ImmutableConflict, InvalidRecord,
                           LABELS, normalize_context)


@pytest.fixture(scope="module")
def repo():
    name = "aevora_test_g1_" + uuid.uuid4().hex
    previous = os.environ.get("AEVORA_FALKORDB_GRAPH")
    os.environ["AEVORA_FALKORDB_GRAPH"] = name
    try:
        repository = GraphRepository.from_environment()
        repository.initialize()
    finally:
        if previous is None:
            os.environ.pop("AEVORA_FALKORDB_GRAPH", None)
        else:
            os.environ["AEVORA_FALKORDB_GRAPH"] = previous
    yield repository
    repository._graph.delete()  # Only this fixture's UUID-named graph is deleted.
    repository.close()


def experience(seed="g1"):
    return {"id": "experience:" + seed, "strategy": "process_local_lock", "title": "Process lock scope",
            "source_type": "synthetic_or_test_fixture", "created_at": "2026-10-11T00:00:00Z",
            "public_summary": "A process lock coordinates shared objects in one process only.",
            "limitations": ["It does not coordinate independent OS workers."]}


def rule(seed="g1"):
    return {"id": "rule:" + seed, "version": "1.0", "public_description": "Compare actual scope facts.",
            "premises": [{"id": "premise:" + seed + ":scope", "fact_key": "concurrency_scope",
                          "allowed_values": ["single_process_threads"], "required": True}]}


def chain(seed="g1", verdict="PASS"):
    return ({"id": "evidence:" + seed, "source_type": "synthetic_or_test_fixture",
             "public_summary": "Synthetic fixture, not a historical Agent run.", "source_run_id": seed},
            {"id": "outcome:" + seed, "run_id": seed, "submission_digest": "a" * 64,
             "evaluator_fingerprint": "b" * 64, "test_suite_fingerprint": "c" * 64,
             "verifier_identity": "test-fixture", "verdict": verdict,
             "private_verification": {"private_path": "/hidden/do-not-export"}},
            {"id": "context:" + seed, "facts": {"concurrency_scope": "single_process_threads",
                                                 "hidden_gold": "do-not-export"}},
            {"id": "task:" + seed, "public_title": "Synthetic process scope fixture"})


def test_empty_real_graph_has_ready_constraints(repo):
    result = repo.initialize()
    assert result["status"] == "READY"
    assert len(result["constraints"]) == len(LABELS) * 2
    assert all(row["status"] == "OPERATIONAL" for row in result["constraints"])


def test_repeat_import_is_exactly_idempotent(repo):
    repo.import_experience(experience(), rule())
    repo.attach_evidence("experience:g1", *chain())
    before = repo.state_fingerprint()
    repo.import_experience(experience(), rule())
    repo.attach_evidence("experience:g1", *chain())
    assert repo.state_fingerprint() == before


def test_multihop_support_is_executed_and_private_fields_projected_out(repo):
    repo.import_experience(experience("paths"), rule("paths"))
    repo.attach_evidence("experience:paths", *chain("paths"))
    paths = repo.snapshot_public_paths("experience:paths")
    assert len(paths) == 1
    assert paths[0]["edge_types"] == ["HAS_REVISION", "SUPPORTED_BY", "VERIFIES", "IN_CONTEXT", "FOR_TASK"]
    assert len(paths[0]["path"]) == 6
    assert "private_verification" not in paths[0]["records"]["VerifiedOutcome"]
    assert "hidden_gold" not in paths[0]["records"]["Context"]["facts"]
    assert "do-not-export" not in str(paths)
    premises = repo.premise_paths("experience:paths")
    assert premises[0]["premise"]["fact_key"] == "concurrency_scope"


def test_same_id_conflict_rejected_and_audited(repo):
    repo.put_node("Task", {"id": "task:immutable", "public_title": "original"})
    with pytest.raises(ImmutableConflict):
        repo.put_node("Task", {"id": "task:immutable", "public_title": "attempted overwrite"})
    assert repo.get_node("Task", "task:immutable")["public_title"] == "original"
    events = repo.query("MATCH (a:AuditEvent) RETURN a.payload_json")
    assert any("task:immutable" in row[0] for row in events)


def test_parameterized_content_is_data_and_does_not_execute(repo):
    text = "' }) DETACH DELETE n // \"\\nInjected"
    repo.put_node("Task", {"id": "task:injection", "public_title": text})
    assert repo.get_node("Task", "task:injection")["public_title"] == text
    assert repo.get_node("Task", "task:immutable") is not None


def test_database_unique_and_mandatory_constraints_really_reject_writes(repo):
    with pytest.raises(GraphUnavailable):
        repo.query("CREATE (:Task {id:$id,payload_json:'{}',payload_sha256:'x'})",
                   {"id": "task:immutable"}, read_only=False)
    with pytest.raises(GraphUnavailable):
        repo.query("CREATE (:Task {payload_json:'{}',payload_sha256:'x'})", read_only=False)


def test_known_counterexample_has_real_negative_path(repo):
    repo.import_experience(experience("negative"), rule("negative"))
    repo.attach_evidence("experience:negative", *chain("negative", "FAIL"), relation="COUNTEREXAMPLE")
    assert repo.snapshot_public_paths("experience:negative")[0]["relation"] == "COUNTEREXAMPLE"


def test_nonbusiness_error_cannot_be_declared_support_or_counterexample(repo):
    repo.import_experience(experience("error"), rule("error"))
    with pytest.raises(InvalidRecord):
        repo.attach_evidence("experience:error", *chain("error", "ERROR"), relation="COUNTEREXAMPLE")
    with pytest.raises(InvalidRecord):
        repo.attach_evidence("experience:error", *chain("error", "FAIL"), relation="SUPPORTED_BY")


def test_query_authority_link_is_scoped_to_actual_run(repo):
    repo.put_node("Query", {"id": "query:run-alpha:1", "run_id": "run-alpha"})
    repo.put_edge("CONSIDERED", "Query", "query:run-alpha:1", "Experience", "experience:g1")
    assert repo.experience_was_resolved("run-alpha", "experience:g1")
    assert not repo.experience_was_resolved("run-beta", "experience:g1")


def test_invalid_schema_identifiers_and_payloads_are_rejected_before_query(repo):
    with pytest.raises(InvalidRecord):
        repo.put_node("Task) DETACH DELETE n", {"id": "valid"})
    with pytest.raises(InvalidRecord):
        repo.put_node("Task", {"id": "bad ' id"})
    with pytest.raises(InvalidRecord):
        repo.put_node("Task", {"id": "valid", "number": float("nan")})
    with pytest.raises(InvalidRecord):
        normalize_context({"concurrency_scope": {"invented": True}})
    assert normalize_context({"concurrency_scope": None}) == {"concurrency_scope": None}


def test_database_disconnected_is_explicit_unavailable_without_fallback(monkeypatch):
    monkeypatch.setenv("AEVORA_FALKORDB_PORT", "1")
    # Official SDK discovery can fail during construction rather than first query.
    with pytest.raises(GraphUnavailable):
        GraphRepository.from_environment().experience_ids()


def test_evidence_context_cannot_be_reinterpreted(repo):
    repo.put_node("Context", {"id": "context:second", "facts": {"concurrency_scope": "independent_processes"}})
    with pytest.raises(ImmutableConflict):
        repo.put_edge("IN_CONTEXT", "VerifiedOutcome", "outcome:g1", "Context", "context:second")
