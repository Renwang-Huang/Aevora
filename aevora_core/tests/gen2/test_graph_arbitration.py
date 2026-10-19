"""Independent expectations; all synthetic records are actually loaded into FalkorDB."""

import copy
import pytest
from aevora.contracts import *
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from tools.validation.g21_fixture import seed, facts, bulk, update_state


def resolve(v2, **kw):
    return resolve_v2(
        v2, facts(v2.registry, **kw), "query:independent-expectation", utc_now()
    )[1]


@pytest.mark.parametrize(
    "outcomes,known,expected,reason",
    [
        (("PASS",), "sqlite_file", "APPLY", "COMPLETE_APPLICABLE_SUPPORT"),
        (("PASS",), None, "VERIFY", "UNKNOWN_REQUIRED_OR_POTENTIAL_EVIDENCE"),
        (("PASS", "FAIL"), "sqlite_file", "VERIFY", "CONFLICT"),
        (("FAIL",), "sqlite_file", "ABSTAIN", "AUTHORITATIVE_BUSINESS_COUNTEREXAMPLE"),
        (("ERROR",), "sqlite_file", "VERIFY", "NO_COMPLETE_APPLICABLE_SUPPORT"),
        (("TIMEOUT",), "sqlite_file", "VERIFY", "NO_COMPLETE_APPLICABLE_SUPPORT"),
        (("NOT_RUN",), "sqlite_file", "VERIFY", "NO_COMPLETE_APPLICABLE_SUPPORT"),
        ((), "sqlite_file", "VERIFY", "NO_COMPLETE_APPLICABLE_SUPPORT"),
    ],
)
def test_truth_table_real_graph(v2, outcomes, known, expected, reason):
    seed(v2, outcomes=outcomes)
    rows = resolve(v2, task__shared_state_kind=known)
    assert rows[0][0]["core_verdict"] == expected
    assert rows[0][0]["reason_codes"] == [reason]
    assert rows[0][1]["completeness"] == "COMPLETE"


def test_lock_scope_hard_precondition(v2):
    seed(v2, required={"task.concurrency_scope": ["single_process_threads"]})
    rec = resolve(
        v2,
        task__shared_state_kind="sqlite_file",
        task__concurrency_scope="independent_processes",
    )[0][0]
    assert rec["core_verdict"] == "ABSTAIN" and rec["reason_codes"] == [
        "HARD_PRECONDITION_VIOLATED"
    ]


def test_foreign_scope_does_not_erase_matching_support(v2):
    seed(v2, "good")
    seed(v2, "other", scope_value="other_engine", outcomes=("FAIL",))
    rows = resolve(v2, task__shared_state_kind="sqlite_file")
    assert len(rows) == 1 and rows[0][0]["core_verdict"] == "APPLY"


def test_withdrawal_is_factual_and_not_edge_deletion(v2):
    seed(v2, withdraw=True)
    assert (
        resolve(v2, task__shared_state_kind="sqlite_file")[0][0]["core_verdict"]
        == "ABSTAIN"
    )


@pytest.mark.parametrize(
    "relation",
    [
        "SUPPORTED_BY",
        "COUNTEREXAMPLE",
        "FOR_TASK",
        "ATTESTED_BY",
        "REQUIRES",
        "USES_RULE",
        "VERIFIES",
        "IN_CONTEXT",
    ],
)
def test_cut_restore_integrity_not_favorable_truncation(v2, relation):
    data = seed(
        v2, outcomes=("PASS", "FAIL") if relation == "COUNTEREXAMPLE" else ("PASS",)
    )
    original = resolve(v2, task__shared_state_kind="sqlite_file")[0][0]
    item = next(e for e in data["edges"] if e["kind"] == relation)
    v2.transport.query(
        "MATCH()-[r {id:$id}]->() DELETE r", dict(id=item["id"]), read_only=False
    )
    with pytest.raises(V2Error, match="GRAPH_INTEGRITY_ERROR"):
        resolve(v2, task__shared_state_kind="sqlite_file")
    v2.put_edge(item)
    restored = resolve(v2, task__shared_state_kind="sqlite_file")[0][0]
    assert original == restored


@pytest.mark.parametrize(
    "kind",
    [
        "Task",
        "Context",
        "Authority",
        "Premise",
        "ExperienceRevision",
        "Evidence",
        "VerifiedOutcome",
    ],
)
def test_bad_sha_or_native_projection_cannot_be_support(v2, kind):
    data = seed(v2)
    n = next(n for n in data["nodes"] if n["kind"] == kind)
    v2.transport.query(
        "MATCH(n:V2Record {id:$id}) SET n.payload_sha256=$bad",
        dict(id=n["id"], bad="0" * 64),
        read_only=False,
    )
    with pytest.raises(V2Error):
        resolve(v2, task__shared_state_kind="sqlite_file")


@pytest.mark.parametrize(
    "change", ["authority", "outcome", "facts", "visibility", "tenant", "phase"]
)
def test_forged_authority_phase_and_scope_rejected(v2, change):
    data = seed(v2)
    current = facts(v2.registry, task__shared_state_kind="sqlite_file")
    if change == "authority":
        v2.registry.authorities.clear()
    elif change == "outcome":
        v2.registry.outcomes.clear()
    elif change == "facts":
        v2.registry.fact_sources.clear()
    else:
        n = copy.deepcopy(next(n for n in data["nodes"] if n["kind"] == "Context"))
        if change == "visibility":
            n["visibility"] = "HOST_ONLY"
        elif change == "tenant":
            n["tenant_id"] = "foreign-tenant"
        else:
            n["facts"]["task.shared_state_kind"]["phase"] = "artifact_after"
        # Attack bypasses host writer; native and canonical digest are coherently changed.
        v2.transport.query(
            "MATCH(n:V2Record {id:$id}) SET n=$p",
            dict(id=n["id"], p=native(n)),
            read_only=False,
        )
    with pytest.raises(V2Error):
        resolve_v2(v2, current, "query:negative", utc_now())


def test_unregistered_verifier_rejected_even_if_label_claimed(v2):
    seed(v2, authority_class="EXTERNAL_UNVERIFIED")
    with pytest.raises(V2Error):
        resolve(v2, task__shared_state_kind="sqlite_file")


def test_staging_is_not_committed(v2):
    seed(v2, staging=True)
    assert resolve(v2, task__shared_state_kind="sqlite_file") == []


def test_empty_graph_has_no_automatic_seed(v2):
    assert resolve(v2, task__shared_state_kind="sqlite_file") == []


def test_missing_commit_manifest_not_a_support_path(v2):
    data = seed(v2)
    v2.transport.query(
        "MATCH(s:TenantState)-[c:COMMITS]->(m) DELETE c", read_only=False
    )
    with pytest.raises(V2Error, match="GRAPH_INTEGRITY_ERROR"):
        resolve(v2, task__shared_state_kind="sqlite_file")


@pytest.mark.parametrize("availability", ["UNKNOWN", "MISSING", "NOT_OBSERVED"])
def test_fact_availability_is_not_known(v2, availability):
    seed(v2)
    fs = facts(v2.registry, task__shared_state_kind=None)
    fs["task.shared_state_kind"]["availability"] = availability
    rec = resolve_v2(v2, fs, "query:unknown", utc_now())[1][0][0]
    assert rec["core_verdict"] == "VERIFY" and rec["unknown_required"] == [
        "task.shared_state_kind"
    ]


def test_bool_is_not_worker_count(v2):
    with pytest.raises(V2Error):
        facts(v2.registry, task__worker_count=True)


@pytest.mark.parametrize(
    "value",
    [
        "2026-13-01T00:00:00Z",
        "2026-10-15",
        "2026-10-15T00:00:00+01:00",
        "2026-10-15T00:00:00",
    ],
)
def test_strict_utc_calendar(value):
    with pytest.raises(V2Error):
        timestamp(value)


@pytest.mark.parametrize("value", [True, 1.0, "1", 0, 4097])
def test_worker_count_is_strict_integer_and_bounded(v2, value):
    with pytest.raises(V2Error):
        facts(v2.registry, task__worker_count=value)
