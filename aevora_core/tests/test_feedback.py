"""Real FalkorDB contract tests with explicitly synthetic OrderFlow evidence.

These tests do not claim native MCP calls, real engineering runs or causal gain.
Each test owns a fresh graph; no production or historical graph is deleted.
"""
from pathlib import Path
import json
import uuid

import pytest

from aevora.feedback import ingest_outcome
from aevora.experience_resolver import ExperienceResolver
from aevora.graph_repository import GraphRepository
from aevora.models import GraphUnavailable, ImmutableConflict, InvalidRecord
from aevora.orderflow_outcome_bridge import OutcomeVerificationError, verify_outcome
from aevora.historical_import import public_context
from test_orderflow_outcome_bridge import Evidence, REPORT, RUN

EXPERIENCE = "experience:feedback-contract-fixture"


@pytest.fixture
def repo(monkeypatch):
    graph_name = "aevora_feedback_test_" + uuid.uuid4().hex
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", graph_name)
    repository = GraphRepository.from_environment()
    repository.initialize()
    yield repository
    assert repository.graph_name == graph_name and graph_name.startswith("aevora_feedback_test_")
    repository._graph.delete()
    repository.close()


def prepared(tmp_path, *, fail=False):
    evidence = Evidence(tmp_path / "archive", fail=fail)
    evidence.report["scenario_version"] = "1.0.0"
    evidence.report["scenario_metadata"] = {
        "metadata": {"title": "Synthetic feedback contract fixture"},
        "runtime": {"topology": "single_process_multi_thread", "database": "sqlite"}}
    evidence.commit()
    return evidence


def experience(repo):
    repo.import_experience({"id": EXPERIENCE, "strategy": "test_fixture_strategy", "title": "Contract fixture",
        "source_type": "synthetic_or_test_fixture", "created_at": "2026-10-11T00:00:00+00:00",
        "public_summary": "Synthetic feedback fixture, not engineering evidence", "limitations": ["Test only"]},
        {"id": "rule:feedback-contract-fixture", "version": "fixture-1", "premises": [
        {"id": "premise:feedback-contract-fixture", "fact_key": "shared_state_kind", "allowed_values": ["sqlite_file"]}]})


def query(repo, *, run_id=RUN, with_edge=True):
    identifier = "query:" + run_id + ":contract-fixture"
    repo.put_node("Query", {"id": identifier, "run_id": run_id,
        "candidate_experience_ids": [EXPERIENCE], "authority": "scoped_broker_run", "synthetic_test_fixture": True})
    if with_edge:
        repo.put_edge("CONSIDERED", "Query", identifier, "Experience", EXPERIENCE)
    return identifier


def decision(repo, query_id, *, identifier="fixture-one", run_id=RUN):
    identifier = "decision:" + run_id + ":" + identifier
    repo.put_node("Decision", {"id": identifier, "run_id": run_id, "query_id": query_id,
        "experience_id": EXPERIENCE, "authority": "UNTRUSTED_PARTICIPANT_CLAIM", "adoption": "CLAIM_ONLY",
        "attribution": "UNKNOWN", "decision": "APPLY", "reason": "Synthetic test claim", "synthetic_test_fixture": True})
    repo.put_edge("RESPONDS_TO", "Decision", identifier, "Query", query_id)
    repo.put_edge("DECIDED", "Decision", identifier, "Experience", EXPERIENCE)
    return identifier


def test_real_graph_feedback_is_observed_not_support(repo, tmp_path):
    evidence = prepared(tmp_path)
    experience(repo)
    qid = query(repo)
    did = decision(repo, qid)
    before = repo.state_fingerprint()
    result = ingest_outcome(repo, evidence.anchor, REPORT)
    assert result["verdict"] == "PASS" and result["attribution"] == "UNKNOWN"
    assert result["feedback_status"] == "outcome_observed_no_attribution"
    assert result["graph"]["graph_sha256"] != before["graph_sha256"]
    assert len(result["receipts"]) == 1
    feedback = repo.get_node("Feedback", result["receipts"][0]["feedback_id"])
    assert feedback["adoption"] == "UNVERIFIED" and feedback["strategy_association"] == "UNVERIFIED"
    assert feedback["untrusted_decision_claims"][0]["id"] == did
    paths = repo.snapshot_public_paths(EXPERIENCE)
    assert len(paths) == 1 and paths[0]["relation"] == "OBSERVED_OUTCOME"
    assert paths[0]["records"]["VerifiedOutcome"]["verdict"] == "PASS"
    assert "private_verification" not in json.dumps(paths)
    assert "test_one" not in json.dumps(paths) and str(tmp_path) not in json.dumps(paths)
    assert repo.get_node("ExperienceRevision", EXPERIENCE + "/revision/initial") is not None
    premise_paths = repo.premise_paths(EXPERIENCE)
    assert len(premise_paths) == 2
    assert len({p["revision"]["id"] for p in premise_paths}) == 2
    assert len({p["rule"]["id"] for p in premise_paths}) == 1
    assert repo.get_node("ObservedAction", result["observed_action_id"])["mental_influence"] == "UNVERIFIED"


def test_same_ingestion_is_idempotent(repo, tmp_path):
    evidence = prepared(tmp_path)
    experience(repo)
    query(repo)
    first = ingest_outcome(repo, evidence.anchor, REPORT)
    second = ingest_outcome(repo, evidence.anchor, REPORT)
    assert first == second
    assert repo.state_fingerprint() == first["graph"]


def test_fail_does_not_become_applicability_counterexample(repo, tmp_path):
    evidence = prepared(tmp_path, fail=True)
    experience(repo)
    query(repo)
    result = ingest_outcome(repo, evidence.anchor, REPORT)
    assert result["verdict"] == "FAIL" and result["attribution"] == "UNKNOWN"
    assert [p["relation"] for p in repo.snapshot_public_paths(EXPERIENCE)] == ["OBSERVED_OUTCOME"]


def test_no_exposure_stores_outcome_without_invented_feedback(repo, tmp_path):
    evidence = prepared(tmp_path)
    result = ingest_outcome(repo, evidence.anchor, REPORT)
    assert result["feedback_status"] == "no_exposure_observed" and not result["receipts"]
    assert repo.get_node("VerifiedOutcome", "orderflow:" + RUN) is not None
    assert repo.query("MATCH (f:Feedback) RETURN f.id") == []


def test_caller_forged_outcome_is_not_authority(repo):
    before = repo.state_fingerprint()
    with pytest.raises(OutcomeVerificationError):
        ingest_outcome(repo, {"verified": True, "verdict": "PASS"}, "evaluation_report.json")
    assert repo.state_fingerprint() == before


@pytest.mark.parametrize("scenario", ["no_query", "no_edge", "different_run"])
def test_explicit_experience_requires_same_run_actual_query_edge(repo, tmp_path, scenario):
    evidence = prepared(tmp_path)
    experience(repo)
    if scenario == "no_edge":
        query(repo, with_edge=False)
    elif scenario == "different_run":
        query(repo, run_id="different-run")
    before = repo.state_fingerprint()
    with pytest.raises(InvalidRecord, match="not queried"):
        ingest_outcome(repo, evidence.anchor, REPORT, experience_ids=[EXPERIENCE])
    assert repo.state_fingerprint() == before


def test_context_cannot_be_changed_to_fit_strategy(repo, tmp_path):
    evidence = prepared(tmp_path)
    before = repo.state_fingerprint()
    with pytest.raises(InvalidRecord, match="context differs"):
        ingest_outcome(repo, evidence.anchor, REPORT, run_context={"concurrency_scope": "independent_processes"})
    assert repo.state_fingerprint() == before


def test_new_claim_cannot_reinterpret_completed_feedback(repo, tmp_path):
    evidence = prepared(tmp_path)
    experience(repo)
    qid = query(repo)
    first = ingest_outcome(repo, evidence.anchor, REPORT)
    feedback_id = first["receipts"][0]["feedback_id"]
    original = repo.get_node("Feedback", feedback_id)
    original_outcome = repo.get_node("VerifiedOutcome", "orderflow:" + RUN)
    decision(repo, qid)
    with pytest.raises(ImmutableConflict):
        ingest_outcome(repo, evidence.anchor, REPORT)
    assert repo.get_node("Feedback", feedback_id) == original
    assert repo.get_node("VerifiedOutcome", "orderflow:" + RUN) == original_outcome
    assert repo.query("MATCH (a:AuditEvent) WHERE a.id STARTS WITH 'conflict:' RETURN a.id")


def test_new_exposure_cannot_rewrite_no_exposure_completion(repo, tmp_path):
    evidence = prepared(tmp_path)
    ingest_outcome(repo, evidence.anchor, REPORT)
    experience(repo)
    query(repo)
    with pytest.raises(ImmutableConflict):
        ingest_outcome(repo, evidence.anchor, REPORT)
    assert repo.query("MATCH (f:Feedback) RETURN f.id") == []


def test_same_run_conflicting_report_rejected_and_audited(repo, tmp_path):
    evidence = prepared(tmp_path)
    first = ingest_outcome(repo, evidence.anchor, REPORT)
    original = repo.get_node("VerifiedOutcome", first["outcome_id"])
    evidence.report["evaluation_ended_at"] = "2026-10-11T00:00:01+00:00"
    evidence.commit()
    with pytest.raises(ImmutableConflict):
        ingest_outcome(repo, evidence.anchor, REPORT)
    assert repo.get_node("VerifiedOutcome", first["outcome_id"]) == original
    assert repo.query("MATCH (a:AuditEvent) WHERE a.id STARTS WITH 'conflict:' RETURN a.id")


def test_new_connection_reads_appended_revision(repo, tmp_path):
    evidence = prepared(tmp_path)
    experience(repo)
    query(repo)
    result = ingest_outcome(repo, evidence.anchor, REPORT)
    again = GraphRepository.from_environment()
    try:
        assert again.state_fingerprint() == result["graph"]
        assert again.snapshot_public_paths(EXPERIENCE) == repo.snapshot_public_paths(EXPERIENCE)
        assert len(again.premise_paths(EXPERIENCE)) == 2
    finally:
        again.close()


def test_observed_pass_changes_evidence_not_support_or_applicability(repo, tmp_path):
    evidence = prepared(tmp_path)
    experience(repo)
    query(repo)
    resolver = ExperienceResolver(repo)
    context = {"shared_state_kind": "sqlite_file", "concurrency_scope": "single_process_threads"}
    before = resolver.resolve(context)
    assert before["candidates"][0]["decision"] == "VERIFY"
    ingest_outcome(repo, evidence.anchor, REPORT)
    after = resolver.resolve(context)
    assert before["graph_snapshot_sha256"] != after["graph_snapshot_sha256"]
    assert after["candidates"][0]["decision"] == "VERIFY"
    assert not after["candidates"][0]["relevant_support_paths"]
    assert not after["candidates"][0]["relevant_counterexample_paths"]
    assert len(after["candidates"][0]["evidence_bundle"]["observed_outcome_paths"]) == 1


def test_existing_outcome_environment_preserved(repo, tmp_path):
    evidence = prepared(tmp_path)
    first = ingest_outcome(repo, evidence.anchor, REPORT)
    rows = repo.query("MATCH (o:VerifiedOutcome {id:$id})-[:IN_CONTEXT]->(c:Context)"
                      "-[:FOR_TASK]->(t:Task) RETURN c.id,t.id", {"id": first["outcome_id"]})
    assert rows == [["context:outcome:" + RUN, "task:outcome:" + RUN]]
    assert ingest_outcome(repo, evidence.anchor, REPORT) == first
    assert repo.query("MATCH (o:VerifiedOutcome {id:$id})-[:IN_CONTEXT]->(c:Context)"
                      "-[:FOR_TASK]->(t:Task) RETURN c.id,t.id", {"id": first["outcome_id"]}) == rows


def test_existing_historical_context_is_reused_not_rewritten(repo, tmp_path):
    evidence = prepared(tmp_path)
    outcome = verify_outcome(evidence.anchor, REPORT)
    context = {"id": "context:history:" + RUN, "facts": public_context("single_process_multi_thread"),
               "source_type": "maintainer_verified_public_runtime"}
    task = {"id": "task:history:" + RUN, "public_title": "Earlier trusted historical environment",
            "scenario_version": "1.0.0"}
    repo.put_node("VerifiedOutcome", outcome)
    repo.put_node("Context", context)
    repo.put_node("Task", task)
    repo.put_edge("IN_CONTEXT", "VerifiedOutcome", outcome["id"], "Context", context["id"])
    repo.put_edge("FOR_TASK", "Context", context["id"], "Task", task["id"])
    result = ingest_outcome(repo, evidence.anchor, REPORT)
    assert repo.get_node("Context", context["id"]) == context
    assert repo.get_node("Task", task["id"]) == task
    assert repo.get_node("Context", "context:outcome:" + RUN) is None
    assert repo.get_node("Task", "task:outcome:" + RUN) is None
    assert ingest_outcome(repo, evidence.anchor, REPORT) == result


def test_interrupted_append_has_no_completion_and_identical_retry_finishes(repo, tmp_path, monkeypatch):
    evidence = prepared(tmp_path)
    experience(repo)
    query(repo)
    original = repo.put_edge

    def interrupted(edge_type, *args, **kwargs):
        if edge_type == "HAS_FEEDBACK":
            raise GraphUnavailable("Deliberate test interruption after actual graph appends")
        return original(edge_type, *args, **kwargs)

    monkeypatch.setattr(repo, "put_edge", interrupted)
    with pytest.raises(GraphUnavailable):
        ingest_outcome(repo, evidence.anchor, REPORT)
    assert repo.get_node("AuditEvent", "ingestion:orderflow:" + RUN) is None
    assert repo.get_node("VerifiedOutcome", "orderflow:" + RUN) is not None
    assert repo.snapshot_public_paths(EXPERIENCE) == []
    monkeypatch.setattr(repo, "put_edge", original)
    completed = ingest_outcome(repo, evidence.anchor, REPORT)
    assert completed["status"] == "INGESTED"
    assert len(repo.snapshot_public_paths(EXPERIENCE)) == 1
    assert ingest_outcome(repo, evidence.anchor, REPORT) == completed
