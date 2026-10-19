"""G2 uses real G1 historical evidence in isolated copied FalkorDB graphs."""
import uuid

import pytest

from aevora.evidence_bundle import build_evidence_bundle
from aevora.experience_resolver import ExperienceResolver
from aevora.graph_repository import GraphRepository
from aevora.historical_import import ATOMIC_ID, LOCK_ID, public_context
from aevora.models import GraphUnavailable, digest


@pytest.fixture
def repo(monkeypatch):
    main = GraphRepository.from_environment()
    assert main.get_node("Experience", ATOMIC_ID) is not None, "Execute G1 verified history import first"
    name = "aevora_test_g2_" + uuid.uuid4().hex
    main._graph.copy(name)
    main.close()
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", name)
    copied = GraphRepository.from_environment()
    yield copied
    copied._graph.delete()
    copied.close()


def result(repo, experience_id, context):
    return next(row for row in ExperienceResolver(repo).resolve(context)["candidates"]
                if row["experience_id"] == experience_id)


def test_same_process_lock_three_states_are_derived_from_actual_context(repo):
    assert result(repo, LOCK_ID, public_context("single_process_multi_thread"))["decision"] == "APPLY"
    d = result(repo, LOCK_ID, public_context("multi_process_shared_sqlite"))
    assert d["decision"] == "ABSTAIN"
    assert d["conflicting_premises"]
    assert d["relevant_counterexample_paths"]
    unknown = result(repo, LOCK_ID, public_context(None))
    assert unknown["decision"] == "VERIFY"
    assert {p["fact_key"] for p in unknown["unknown_premises"]} == {"concurrency_scope", "synchronization_scope"}


@pytest.mark.parametrize("topology", ["single_process_multi_thread", "multi_process_shared_sqlite"])
def test_atomic_sql_uses_distinct_real_support_without_episode_branch(repo, topology):
    row = result(repo, ATOMIC_ID, public_context(topology))
    assert row["decision"] == "APPLY"
    assert row["relevant_support_paths"]
    scopes = {p["records"]["Context"]["facts"]["concurrency_scope"] for p in row["relevant_support_paths"]}
    assert scopes == {public_context(topology)["concurrency_scope"]}
    assert row["attribution"] == "UNKNOWN"


def test_episode_names_do_not_change_results(repo):
    context = public_context("multi_process_shared_sqlite")
    left = ExperienceResolver(repo).resolve({**context, "episode_id": "A"})
    right = ExperienceResolver(repo).resolve({**context, "episode_id": "D"})
    assert [(r["experience_id"], r["decision"], r["reason"]) for r in left["candidates"]] == [
        (r["experience_id"], r["decision"], r["reason"]) for r in right["candidates"]]
    assert left["graph_snapshot_sha256"] == right["graph_snapshot_sha256"]


def test_deleting_relevant_support_edge_changes_apply_to_verify(repo):
    before = result(repo, ATOMIC_ID, public_context("multi_process_shared_sqlite"))
    actual = before["relevant_support_paths"][0]
    repo.query("MATCH (r:ExperienceRevision {id:$r})-[link:SUPPORTED_BY]->(e:Evidence {id:$e}) DELETE link",
               {"r": actual["records"]["ExperienceRevision"]["id"], "e": actual["records"]["Evidence"]["id"]}, read_only=False)
    after = result(repo, ATOMIC_ID, public_context("multi_process_shared_sqlite"))
    assert after["decision"] == "VERIFY"
    assert after["reason"] == "NO_RELEVANT_COMPLETE_VERIFIED_SUPPORT"
    assert before["retrieval_snapshot_sha256"] != after["retrieval_snapshot_sha256"]
    assert result(repo, ATOMIC_ID, public_context("single_process_multi_thread"))["decision"] == "APPLY"


def test_deleted_required_premise_cannot_strengthen_a_recommendation(repo):
    before = result(repo, LOCK_ID, public_context("single_process_multi_thread"))
    assert before["decision"] == "APPLY"
    repo.query("MATCH (rule:Rule)-[r:REQUIRES]->(p:Premise {id:$p}) DELETE r",
               {"p": "premise:lock:topology"}, read_only=False)
    after = result(repo, LOCK_ID, public_context("single_process_multi_thread"))
    assert after["decision"] == "VERIFY"
    assert after["graph_integrity_issues"]
    assert after["retrieval_snapshot_sha256"] != before["retrieval_snapshot_sha256"]


def test_deleted_outcome_task_hop_removes_true_support_chain(repo):
    before = result(repo, ATOMIC_ID, public_context("multi_process_shared_sqlite"))
    context_id = before["relevant_support_paths"][0]["records"]["Context"]["id"]
    repo.query("MATCH (c:Context {id:$id})-[r:FOR_TASK]->(t:Task) DELETE r", {"id": context_id}, read_only=False)
    after = result(repo, ATOMIC_ID, public_context("multi_process_shared_sqlite"))
    assert after["decision"] == "VERIFY"
    assert not after["relevant_support_paths"]


def test_adding_actual_rlock_counterexample_changes_conservative_output(repo):
    # A controlled rule fixture starts without claiming verified cross-process
    # support. Adding the actual historical same-strategy D failure changes
    # VERIFY to ABSTAIN; it is not a fabricated business result.
    broad_id = "experience:controlled-broad-rlock-rule"
    original = repo.get_node("Experience", LOCK_ID)
    copied = {**original, "id": broad_id, "created_at": "2026-10-11T00:00:00Z",
              "source_type": "synthetic_or_test_fixture", "title": "Controlled rule generalization fixture"}
    rule = {"id": "rule:controlled-broad-lock", "version": "test-fixture/1",
            "premises": [{"id": "premise:controlled-lock:scope", "fact_key": "concurrency_scope",
                          "allowed_values": ["single_process_threads", "independent_processes"]},
                         {"id": "premise:controlled-lock:sync", "fact_key": "synchronization_scope",
                          "allowed_values": ["shared_process_object", "per_process"]}]}
    repo.import_experience(copied, rule)
    original_paths = repo.snapshot_public_paths(LOCK_ID)
    positive = next(p for p in original_paths if p["relation"] == "SUPPORTED_BY")
    negative = next(p for p in original_paths if p["relation"] == "COUNTEREXAMPLE")
    def attach(path, relation):
        records = path["records"]
        values = [repo.get_node(label, records[label]["id"]) for label in ("Evidence", "VerifiedOutcome", "Context", "Task")]
        repo.attach_evidence(broad_id, *values, relation=relation)
    attach(positive, "SUPPORTED_BY")
    before = result(repo, broad_id, public_context("multi_process_shared_sqlite"))
    assert before["decision"] == "VERIFY"
    attach(negative, "COUNTEREXAMPLE")
    after = result(repo, broad_id, public_context("multi_process_shared_sqlite"))
    assert after["decision"] == "ABSTAIN"
    assert after["reason"] == "MATCHING_VERIFIED_COUNTEREXAMPLE"
    assert after["relevant_counterexample_paths"][0]["records"]["VerifiedOutcome"]["run_id"] == negative["records"]["VerifiedOutcome"]["run_id"]
    assert after["retrieval_snapshot_sha256"] != before["retrieval_snapshot_sha256"]


def test_unrelated_state_and_unproven_topology_do_not_get_apply(repo):
    unknown = result(repo, ATOMIC_ID, {**public_context("multi_process_shared_sqlite"), "concurrency_scope": "distributed_services"})
    assert unknown["decision"] == "VERIFY"
    unrelated = result(repo, ATOMIC_ID, {**public_context("multi_process_shared_sqlite"), "shared_state_kind": "unrelated_in_memory_state"})
    assert unrelated["decision"] == "ABSTAIN"
    assert unrelated["conflicting_premises"]


def test_public_bundle_has_versions_and_no_private_evaluation_data(repo):
    bundle = build_evidence_bundle(repo, ATOMIC_ID)
    assert bundle["status"] == "AVAILABLE"
    assert bundle["revision_ids"] and bundle["premise_paths"] and len(bundle["support_paths"]) == 2
    raw = str(bundle)
    for forbidden in ("private_verification", "source_reference", "private_manifest", "test_counts", "hidden_tests/", "reference_patches/"):
        assert forbidden not in raw
    assert bundle["retrieval_snapshot_sha256"] == digest({"experience": bundle["experience"], "premise_paths": bundle["premise_paths"], "paths": bundle["paths"]})


def test_natural_origin_is_distinct_from_each_historical_replay(repo):
    bundle = build_evidence_bundle(repo, ATOMIC_ID)
    source = repo.get_node("Experience", ATOMIC_ID)
    assert bundle["experience"]["origin_run_id"] == source["origin_run_id"]
    assert bundle["experience"]["origin_patch_sha256"] == source["origin_patch_sha256"]
    replay_runs = {path["records"]["VerifiedOutcome"]["run_id"] for path in bundle["support_paths"]}
    assert len(replay_runs) == 2
    assert bundle["experience"]["origin_run_id"] not in replay_runs
    assert all(path["records"]["VerifiedOutcome"]["source_type"] == "historical_replay"
               for path in bundle["support_paths"])


def test_query_records_alone_do_not_fake_changed_experience_snapshot(repo):
    before = ExperienceResolver(repo).resolve(public_context("multi_process_shared_sqlite"))
    repo.put_node("Query", {"id": "query:unrelated:1", "run_id": "unrelated", "claim": "Queried does not equal adopted"})
    after = ExperienceResolver(repo).resolve(public_context("multi_process_shared_sqlite"))
    assert before["graph_snapshot_sha256"] == after["graph_snapshot_sha256"]


def test_empty_actual_graph_cannot_unconditionally_apply(monkeypatch):
    monkeypatch.setenv("AEVORA_FALKORDB_GRAPH", "aevora_test_empty_" + uuid.uuid4().hex)
    repository = GraphRepository.from_environment()
    repository.initialize()
    try:
        result = ExperienceResolver(repository).resolve(public_context("multi_process_shared_sqlite"))
        assert result["status"] == "AVAILABLE"
        assert result["candidates"] == []
    finally:
        repository._graph.delete()
        repository.close()


def test_disconnected_database_is_not_a_resolver_fallback(monkeypatch):
    monkeypatch.setenv("AEVORA_FALKORDB_PORT", "1")
    with pytest.raises(GraphUnavailable):
        ExperienceResolver(GraphRepository.from_environment()).resolve(public_context("multi_process_shared_sqlite"))


def test_false_and_zero_remain_known_different_values(repo):
    false = result(repo, LOCK_ID, {**public_context("single_process_multi_thread"), "concurrency_scope": False})
    zero = result(repo, LOCK_ID, {**public_context("single_process_multi_thread"), "concurrency_scope": 0})
    assert false["decision"] == zero["decision"] == "ABSTAIN"
    assert not false["unknown_premises"] and not zero["unknown_premises"]
