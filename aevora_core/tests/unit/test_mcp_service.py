"""Synthetic contract fixtures; these tests do not claim live graph evidence."""

from __future__ import annotations

from copy import deepcopy
import pytest

from aevora.mcp_server import ExperienceService, create_server
from aevora.models import GraphUnavailable, ImmutableConflict, digest


class SyntheticRepository:
    def __init__(self):
        self.nodes = {("Experience", "experience:test"): {"id": "experience:test"}}
        self.edges = set()

    def put_node(self, label, payload):
        key = (label, payload["id"])
        if key in self.nodes and self.nodes[key] != payload:
            raise ImmutableConflict("Synthetic immutable conflict")
        self.nodes[key] = deepcopy(payload)
        return {"id": payload["id"], "payload_sha256": digest(payload)}

    def get_node(self, label, identifier):
        return deepcopy(self.nodes.get((label, identifier)))

    def put_edge(self, relation, source_label, source, target_label, target):
        assert (source_label, source) in self.nodes and (
            target_label,
            target,
        ) in self.nodes
        self.edges.add((relation, source_label, source, target_label, target))

    def experience_was_resolved(self, run_id, experience_id):
        return any(
            label == "Query"
            and record.get("run_id") == run_id
            and experience_id in record.get("candidate_experience_ids", [])
            for (label, _), record in self.nodes.items()
        )


class SyntheticResolver:
    def __init__(self, _):
        pass

    def resolve(self, context):
        return {
            "status": "AVAILABLE",
            "query_version": "synthetic-contract-only",
            "graph_snapshot_sha256": digest(context),
            "candidates": [{"experience_id": "experience:test", "decision": "VERIFY"}],
        }


def service(repo=None, run_id="run-a"):
    return ExperienceService(
        run_id=run_id,
        public_context={"concurrency_scope": "single_process_threads"},
        repository=repo or SyntheticRepository(),
        resolver_factory=SyntheticResolver,
        bundle_builder=lambda _repo, experience_id: {
            "experience_id": experience_id,
            "source": "synthetic_contract_only",
        },
    )


def claim(query, **changes):
    result = {
        "query_id": query["query_id"],
        "experience_id": "experience:test",
        "decision": "VERIFY",
        "reason": "Inspect unknown transaction semantics",
        "verification_steps": ["Run the public regression"],
    }
    result.update(changes)
    return result


def test_query_is_persisted_and_bound_to_actual_run():
    instance = service()
    result = instance.resolve_experience({"transaction_guarantees": None})
    query = instance.repository.get_node("Query", result["query_id"])
    assert query["run_id"] == "run-a"
    assert "transaction_guarantees" not in query["task_context"]
    assert query["participant_claims"]["transaction_guarantees"] is None
    assert result["participant_claims"] == query["participant_claims"]
    assert (
        result["participant_claims_status"] == "UNVERIFIED_NOT_USED_FOR_APPLICABILITY"
    )
    assert query["authority"] == "scoped_broker_run"
    assert result["query_id"].startswith("query:run-a:")
    assert any(edge[0] == "CONSIDERED" for edge in instance.repository.edges)


@pytest.mark.parametrize(
    "claims",
    [
        {"run_id": "foreign"},
        {"cypher": "MATCH(n)"},
        {"concurrency_scope": "different"},
        {"private_manifest": "/secret"},
        {"worker_count_known": {"value": 4}},
    ],
)
def test_context_cannot_change_pinned_environment_or_authority(claims):
    with pytest.raises(ValueError):
        service().resolve_experience(claims)


def test_pinned_boolean_is_not_interchangeable_with_integer():
    instance = ExperienceService(
        run_id="run-a",
        public_context={"worker_count_known": False},
        repository=SyntheticRepository(),
        resolver_factory=SyntheticResolver,
        bundle_builder=lambda *args: {},
    )
    with pytest.raises(ValueError):
        instance.resolve_experience({"worker_count_known": 0})


def test_unknown_sentinel_uses_same_semantics_as_resolver():
    instance = ExperienceService(
        run_id="run-a",
        public_context={"concurrency_scope": " UnAvAiLaBlE "},
        repository=SyntheticRepository(),
        resolver_factory=SyntheticResolver,
        bundle_builder=lambda *args: {},
    )
    query = instance.resolve_experience({"concurrency_scope": "single_process_threads"})
    record = instance.repository.get_node("Query", query["query_id"])
    assert record["task_context"]["concurrency_scope"] == " UnAvAiLaBlE "
    assert record["participant_claims"]["concurrency_scope"] == "single_process_threads"
    assert record["pinned_public_context"]["concurrency_scope"] == " UnAvAiLaBlE "


@pytest.mark.parametrize(
    "pinned", [{}, {"concurrency_scope": None}, {"concurrency_scope": "UNKNOWN"}]
)
def test_untrusted_claim_cannot_establish_missing_applicability_fact(pinned):
    class RecordingResolver(SyntheticResolver):
        def resolve(self, context):
            self.received_context = deepcopy(context)
            return super().resolve(context)

    instance = ExperienceService(
        run_id="run-a",
        public_context=pinned,
        repository=SyntheticRepository(),
        resolver_factory=RecordingResolver,
        bundle_builder=lambda *args: {},
    )
    claims = {"concurrency_scope": "single_process_threads", "worker_count_known": True}
    result = instance.resolve_experience(claims)
    assert instance.resolver.received_context == pinned
    query = instance.repository.get_node("Query", result["query_id"])
    assert query["task_context"] == pinned and query["pinned_public_context"] == pinned
    assert (
        query["participant_claims"] == claims and result["participant_claims"] == claims
    )
    assert result["context_authority"] == "TRUSTED_PINNED_PUBLIC_FACTS_ONLY"
    assert (
        result["participant_claims_status"] == "UNVERIFIED_NOT_USED_FOR_APPLICABILITY"
    )


def test_exact_known_claim_is_allowed_without_changing_authority():
    instance = service()
    claim = {"concurrency_scope": "single_process_threads"}
    result = instance.resolve_experience(claim)
    query = instance.repository.get_node("Query", result["query_id"])
    assert query["task_context"] == query["pinned_public_context"] == claim
    assert result["participant_claims"] == claim


def test_unqueried_experience_bundle_is_unauthorized():
    with pytest.raises(ValueError):
        service().build_evidence_bundle("experience:test")


def test_same_run_sdk_connections_can_share_actual_query_authority():
    repository = SyntheticRepository()
    first, second = service(repository), service(repository)
    query = first.resolve_experience({})
    assert (
        second.build_evidence_bundle("experience:test")["source"]
        == "synthetic_contract_only"
    )
    result = second.record_decision(claim(query))
    assert result["status"] == "RECORDED_UNTRUSTED"
    assert result["trusted_outcome"] == "NOT_SUBMITTED"
    assert result["attribution"] == "UNKNOWN"
    stored = repository.get_node("Decision", result["decision_id"])
    assert stored["authority"] == "UNTRUSTED_PARTICIPANT_CLAIM"
    assert stored["agent_thread_id"] == "UNAVAILABLE"
    assert not any(label == "VerifiedOutcome" for label, _ in repository.nodes)


def test_cross_run_query_and_bundle_are_rejected():
    repository = SyntheticRepository()
    query = service(repository).resolve_experience({})
    other = service(repository, run_id="run-b")
    with pytest.raises(ValueError):
        other.record_decision(claim(query))
    with pytest.raises(ValueError):
        other.build_evidence_bundle("experience:test")


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": "run-a"},
        {"verified": True},
        {"verdict": "PASS"},
        {"overall_status": "PASS"},
        {"feedback": "promote"},
        {"experience_id": "experience:unreturned"},
        {"query_id": "query:nonexistent"},
        {"decision": "VERIFY", "verification_steps": []},
        {"decision": "PASS"},
        {"reason": ""},
        {"decision_id": "decision:run-b:forged"},
    ],
)
def test_decision_does_not_grant_outcome_or_foreign_authority(changes):
    instance = service()
    query = instance.resolve_experience({})
    with pytest.raises(ValueError):
        instance.record_decision(claim(query, **changes))


def test_explicit_decision_id_is_idempotent_and_conflicting_claim_rejected():
    instance = service()
    query = instance.resolve_experience({})
    value = claim(query, decision_id="decision:run-a:test")
    first = instance.record_decision(value)
    assert instance.record_decision(value) == first
    with pytest.raises(ImmutableConflict):
        instance.record_decision({**value, "reason": "Different bytes"})


def test_database_unavailability_does_not_create_query_or_fallback():
    instance = service()

    class DisconnectedResolver:
        def resolve(self, _):
            raise GraphUnavailable("Synthetic disconnected fixture")

    instance.resolver = DisconnectedResolver()
    with pytest.raises(GraphUnavailable):
        instance.resolve_experience({})
    assert not any(label == "Query" for label, _ in instance.repository.nodes)


def test_official_sdk_server_identity_and_tool_catalog():
    import anyio

    async def inspect():
        server = create_server(service())
        tools = await server.list_tools()
        assert server.name == "Aevora"
        assert {tool.name for tool in tools} == {
            "resolve_experience",
            "build_evidence_bundle",
            "record_decision",
            "record_observation_use",
            "search_observations",
            "read_observation_sources",
        }
        assert all("submit_outcome" not in tool.name for tool in tools)
        report_tool = next(tool for tool in tools if tool.name == "record_observation_use")
        report = report_tool.inputSchema["$defs"]["ObservationUseReport"]
        assert report["properties"]["purpose"]["enum"] == [
            "DEBUGGING", "PLANNING", "IMPLEMENTATION", "VALIDATION", "OTHER"
        ]
        assert report["properties"]["disposition"]["enum"] == [
            "INVESTIGATED", "REUSED", "REJECTED", "NOT_RELEVANT", "INCONCLUSIVE"
        ]
        assert set(report["required"]) == {"candidate_id", "report_key", "purpose", "disposition", "reason"}
        assert report["additionalProperties"] is False
        assert report["properties"]["elapsed_seconds"]["type"] == "integer"
        assert "default" not in report["properties"]["elapsed_seconds"]

    anyio.run(inspect)
