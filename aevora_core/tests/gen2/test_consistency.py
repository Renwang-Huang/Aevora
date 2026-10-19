"""Controlled real database interleavings, not simulated graph results."""

import copy
import pytest
from aevora.contracts import *
from aevora.models import utc_now
from aevora.experience_resolver import resolve_v2
from aevora.graph_repository import GraphRepository
from tools.validation.g21_fixture import seed, facts, bulk, update_state


@pytest.mark.parametrize("changes", [1, 2])
def test_epoch_retry_once_or_refuse_mixed_read(v2, monkeypatch, changes):
    seed(v2)
    original = v2.read_witness
    remaining = changes
    calls = 0

    def interleave(*args):
        nonlocal remaining, calls
        calls += 1
        value = original(*args)
        if remaining:
            remaining -= 1
            update_state(v2, epoch=v2.state()["epoch"] + 1)
        return value

    monkeypatch.setattr(v2, "read_witness", interleave)
    current = facts(v2.registry, task__shared_state_kind="sqlite_file")
    if changes == 2:
        with pytest.raises(V2Error, match="GRAPH_CHANGED"):
            v2.resolve_witnesses(current)
    else:
        state, witnesses = v2.resolve_witnesses(current)
        assert calls == 2 and witnesses[0]["epoch"] == state["epoch"] == 2


def test_wrong_profile_factory_and_physical_tenant(v2):
    with pytest.raises(V2Error, match="UNAUTHORIZED"):
        TenantBinding("tenant-g21", "legacy_graph")
    with pytest.raises(V2Error):
        v2.transport.v2(
            TenantBinding("other-tenant", v2.binding.graph_name), TrustRegistry()
        ).state()


def test_new_graph_initializer_never_upgrades_legacy(v2):
    # Host explicitly creates a separate legacy graph then deliberately misuses v2.
    main = v2.transport
    other = GraphRepository(
        host="127.0.0.1",
        port=main._client.connection.connection_pool.connection_kwargs["port"],
        password=main._client.connection.connection_pool.connection_kwargs["password"],
        graph_name=v2.binding.graph_name + "_legacy",
    )
    other.initialize()
    before = other.state_fingerprint()
    with pytest.raises(V2Error):
        other.v2(
            TenantBinding(v2.tenant, other.graph_name), TrustRegistry()
        ).initialize()
    assert other.state_fingerprint() == before
    other.close()


def test_actual_disconnected_db_no_fallback(v2):
    from aevora.models import GraphUnavailable

    with pytest.raises(GraphUnavailable):
        GraphRepository(
            host="127.0.0.1",
            port=1,
            graph_name="aevora_v2_unavailable",
            password="deliberately-invalid-probe",
        )


def test_new_manifest_cannot_redefine_registered_source(v2):
    data = seed(v2)
    v2.registry.publications.clear()
    with pytest.raises(V2Error):
        v2.resolve_witnesses(facts(v2.registry, task__shared_state_kind="sqlite_file"))


def test_multiple_legal_apply_without_score(v2):
    seed(v2, "one")
    seed(v2, "two")
    rows = resolve_v2(
        v2,
        facts(v2.registry, task__shared_state_kind="sqlite_file"),
        "query:two",
        utc_now(),
    )[1]
    assert len(rows) == 2 and all(r["core_verdict"] == "APPLY" for r, w in rows)
    assert [r["experience_id"] for r, w in rows] == sorted(
        r["experience_id"] for r, w in rows
    )


@pytest.mark.parametrize("attack", ["counter", "governance", "payload", "native"])
def test_manifest_completeness_and_projection_negative(v2, attack):
    data = seed(v2, outcomes=("PASS", "FAIL"), withdraw=attack == "governance")
    if attack in {"counter", "governance"}:
        target = next(
            e
            for e in data["edges"]
            if e["kind"] == ("COUNTEREXAMPLE" if attack == "counter" else "GOVERNS")
        )
        v2.transport.query(
            "MATCH()-[r {id:$id}]->() DELETE r", dict(id=target["id"]), read_only=False
        )
    elif attack == "payload":
        n = data["experience"]
        v2.transport.query(
            "MATCH(n {id:$id}) SET n.payload_json=$bad",
            dict(id=n["id"], bad='{"id":1,"id":2}'),
            read_only=False,
        )
    else:
        n = data["experience"]
        v2.transport.query(
            "MATCH(n {id:$id}) SET n.tenant_id=$bad",
            dict(id=n["id"], bad="another-tenant"),
            read_only=False,
        )
    with pytest.raises(V2Error):
        v2.resolve_witnesses(facts(v2.registry, task__shared_state_kind="sqlite_file"))


@pytest.mark.parametrize(
    "availability,value,expected",
    [
        ("KNOWN", "single_process_threads", "APPLY"),
        ("KNOWN", "independent_processes", "ABSTAIN"),
        ("UNKNOWN", None, "VERIFY"),
    ],
)
def test_committed_scope_restriction_is_enforced(v2, availability, value, expected):
    from tools.validation.g21_fixture import seal_closure

    data = seed(v2)
    g = record(
        v2.tenant,
        "GovernanceEvent",
        "restrict",
        event_type="restrict_scope",
        effective_at="2026-10-15T00:00:00Z",
        scope={"task.concurrency_scope": ["single_process_threads"]},
        target_id=data["revision"]["id"],
        target_label="ExperienceRevision",
    )
    seal_closure(
        v2,
        "restricted-manifest",
        data["experience"],
        data["nodes"] + [g],
        data["edges"] + [edge(v2.tenant, "GOVERNS", g, data["revision"])],
    )
    current = facts(
        v2.registry,
        task__shared_state_kind="sqlite_file",
        task__concurrency_scope=value,
    )
    rec = resolve_v2(v2, current, "query:restriction", utc_now())[1][0][0]
    assert rec["core_verdict"] == expected


def test_supersedes_is_explicit_and_no_timestamp_winner(v2):
    from tools.validation.g21_fixture import seal_closure

    data = seed(v2)
    old = data["revision"]
    rule = data["rule"]
    exp = data["experience"]
    new = record(
        v2.tenant,
        "ExperienceRevision",
        "next",
        experience_id=exp["id"],
        revision_kind="rule_publication",
        declared_rule_id=rule["id"],
        supersedes_ids=[old["id"]],
        scope=old["scope"],
        valid_from="2026-10-15T00:00:00Z",
    )
    e1 = edge(v2.tenant, "HAS_REVISION", exp, new)
    e2 = edge(v2.tenant, "USES_RULE", new, rule)
    e3 = edge(v2.tenant, "SUPERSEDES", new, old)
    seal_closure(
        v2,
        "superseded-manifest",
        exp,
        data["nodes"] + [new],
        data["edges"] + [e1, e2, e3],
    )
    rec = resolve_v2(
        v2,
        facts(v2.registry, task__shared_state_kind="sqlite_file"),
        "query:revision",
        utc_now(),
    )[1][0][0]
    assert rec["revision_ids"] == [new["id"]] and rec["core_verdict"] == "VERIFY"
    assert rec["reason_codes"] == ["NO_COMPLETE_APPLICABLE_SUPPORT"]


def test_fact_phase_mismatch_rejected_before_graph(v2):
    value = facts(v2.registry, task__shared_state_kind="sqlite_file")[
        "task.shared_state_kind"
    ]
    value["phase"] = "artifact_after"
    with pytest.raises(V2Error):
        fact(value)


@pytest.mark.parametrize("kind", ["Task", "Authority", "Evidence"])
def test_namespaced_identity_recomputed_from_stable_key(v2, kind):
    value = copy.deepcopy(next(n for n in seed(v2)["nodes"] if n["kind"] == kind))
    value["id"] = identity("other-tenant", kind, value["identity_key"])
    with pytest.raises(V2Error):
        validate_record(value, v2.tenant)


@pytest.mark.parametrize("kind", ["GovernanceEvent", "ExperienceRevision"])
def test_prepared_governance_or_revision_remains_invisible(v2, kind):
    data = seed(v2)
    if kind == "GovernanceEvent":
        staged = record(
            v2.tenant,
            kind,
            "staged",
            event_type="withdraw",
            effective_at="2026-10-15T00:00:00Z",
            scope=data["revision"]["scope"],
            target_id=data["revision"]["id"],
            target_label="ExperienceRevision",
        )
        links = [edge(v2.tenant, "GOVERNS", staged, data["revision"])]
    else:
        staged = record(
            v2.tenant,
            kind,
            "staged",
            experience_id=data["experience"]["id"],
            revision_kind="rule_publication",
            declared_rule_id=data["rule"]["id"],
            supersedes_ids=[],
            scope=data["revision"]["scope"],
            valid_from="2026-10-15T00:00:00Z",
        )
        links = [
            edge(v2.tenant, "HAS_REVISION", data["experience"], staged),
            edge(v2.tenant, "USES_RULE", staged, data["rule"]),
        ]
    bulk(v2, [staged], links)
    result = resolve_v2(
        v2,
        facts(v2.registry, task__shared_state_kind="sqlite_file"),
        "query:staging-active",
        utc_now(),
    )[1]
    assert result[0][0]["core_verdict"] == "APPLY"
    assert staged["id"] not in result[0][1]["nodes"]


def test_product_record_creation_time_is_actual_utc():
    from datetime import datetime, timezone

    before = datetime.now(timezone.utc)
    value = record("tenant-g21", "Task", "timestamp-proof", facts={})
    after = datetime.now(timezone.utc)
    assert before <= timestamp(value["created_at"]) <= after


def test_native_scope_index_damage_cannot_silently_omit_counter_candidate(v2):
    seed(v2, "valid-support")
    counter = seed(v2, "counter-candidate", outcomes=("FAIL",))
    # Actual payload still declares current scope, but the indexed native projection is damaged.
    v2.transport.query(
        "MATCH(e:Experience {id:$id}) SET e.scope_token=$wrong",
        dict(id=counter["experience"]["id"], wrong="damaged-unrelated-partition"),
        read_only=False,
    )
    raw = v2.transport.query("MATCH(e:Experience) RETURN e.payload_json")
    assert len(raw) == 2
    with pytest.raises(V2Error, match="GRAPH_INTEGRITY_ERROR"):
        v2.resolve_witnesses(facts(v2.registry, task__shared_state_kind="sqlite_file"))


@pytest.mark.parametrize("hops", [8, 9])
def test_real_supersedes_hop_boundary(v2, hops):
    from tools.validation.g21_fixture import seal_closure

    data = seed(v2)
    nodes = list(data["nodes"])
    edges = list(data["edges"])
    old = data["revision"]
    rule = data["rule"]
    exp = data["experience"]
    for i in range(1, hops + 1):
        nxt = record(
            v2.tenant,
            "ExperienceRevision",
            ["chain", i],
            experience_id=exp["id"],
            revision_kind="rule_publication",
            declared_rule_id=rule["id"],
            supersedes_ids=[old["id"]],
            scope=old["scope"],
            valid_from="2026-10-15T00:00:00Z",
        )
        nodes.append(nxt)
        edges.extend(
            [
                edge(v2.tenant, "HAS_REVISION", exp, nxt),
                edge(v2.tenant, "USES_RULE", nxt, rule),
                edge(v2.tenant, "SUPERSEDES", nxt, old),
            ]
        )
        old = nxt
    seal_closure(v2, "chain-root", exp, nodes, edges)
    current = facts(v2.registry, task__shared_state_kind="sqlite_file")
    if hops == 9:
        with pytest.raises(V2Error):
            v2.resolve_witnesses(current)
    else:
        state, w = v2.resolve_witnesses(current)
        assert w[0]["completeness"] == "COMPLETE"


def test_real_supersedes_cycle_denied(v2):
    from tools.validation.g21_fixture import seal_closure

    data = seed(v2)
    exp = data["experience"]
    rule = data["rule"]
    aid = identity(v2.tenant, "ExperienceRevision", "cycle-a")
    bid = identity(v2.tenant, "ExperienceRevision", "cycle-b")
    extra = []
    links = []
    for key, other in [("cycle-a", bid), ("cycle-b", aid)]:
        r = record(
            v2.tenant,
            "ExperienceRevision",
            key,
            experience_id=exp["id"],
            revision_kind="rule_publication",
            declared_rule_id=rule["id"],
            supersedes_ids=[other],
            scope=data["revision"]["scope"],
            valid_from="2026-10-15T00:00:00Z",
        )
        extra.append(r)
        links.extend(
            [
                edge(v2.tenant, "HAS_REVISION", exp, r),
                edge(v2.tenant, "USES_RULE", r, rule),
            ]
        )
    links.extend(
        [
            edge(v2.tenant, "SUPERSEDES", extra[0], extra[1]),
            edge(v2.tenant, "SUPERSEDES", extra[1], extra[0]),
        ]
    )
    seal_closure(v2, "cycle-root", exp, data["nodes"] + extra, data["edges"] + links)
    with pytest.raises(V2Error):
        v2.resolve_witnesses(facts(v2.registry, task__shared_state_kind="sqlite_file"))
