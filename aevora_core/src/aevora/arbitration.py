"""Deterministic v2 extension: actual validated witnesses, no global score or ID table."""

from __future__ import annotations
from .contracts import POLICY, require, validate_schema, digest, identity
from .governance import project, scope_relation, equal


def flat(facts):
    return {
        k: v["value"]
        if v["availability"] == "KNOWN"
        else "not_observed"
        if v["availability"] == "NOT_OBSERVED"
        else None
        for k, v in facts.items()
    }


def arbitrate(witness, facts, query_id, as_of):
    require(witness["completeness"] == "COMPLETE")
    nodes = witness["nodes"]
    edges = witness["edges"]
    context = flat(facts)

    def targets(identifier, kind):
        return [
            nodes[e["target_id"]]
            for e in edges.values()
            if e["source_id"] == identifier and e["kind"] == kind
        ]

    revisions = [n for n in nodes.values() if n["kind"] == "ExperienceRevision"]
    view = {
        "revisions": [
            dict(
                record=r,
                complete=True,
                rule_ids=[n["id"] for n in targets(r["id"], "USES_RULE")],
            )
            for r in revisions
        ],
        "supersedes": [
            dict(new_id=e["source_id"], old_id=e["target_id"])
            for e in edges.values()
            if e["kind"] == "SUPERSEDES"
        ],
        "events": [
            dict(record=n, complete=True, edge_present=True)
            for n in nodes.values()
            if n["kind"] == "GovernanceEvent"
        ],
    }
    governance = project(view, context, as_of)
    active = governance["selected_revision_ids"]
    rules = [nodes[i] for i in governance["selected_rule_ids"]]
    verdict = "VERIFY"
    reasons = []
    unknown = []
    matched = []
    conflicting = []
    support = []
    counter = []
    potential = []
    necessary = []
    unknown.extend(
        k
        for row in governance["uncertain_records"]
        for k in row.get("unknown_facts", [])
    )
    for rule in rules:
        for pre in targets(rule["id"], "REQUIRES"):
            current = facts.get(pre["fact_key"])
            if pre["mode"] == "necessary":
                necessary.append(pre)
            if not current or current["availability"] != "KNOWN":
                unknown.append(pre["fact_key"])
                continue
            match = any(equal(current["value"], v) for v in pre["allowed_values"])
            if match if pre["mode"] == "necessary" else not match:
                matched.append(pre["id"])
            else:
                conflicting.append(pre["id"])
    for r in revisions:
        if r["id"] not in active:
            continue
        rule = targets(r["id"], "USES_RULE")[0]
        for relation, output in [
            ("SUPPORTED_BY", support),
            ("COUNTEREXAMPLE", counter),
        ]:
            for ev in targets(r["id"], relation):
                if ev["id"] in governance["excluded_target_ids"]:
                    continue
                restrictions = [
                    v
                    for v in governance["path_scope_checks"]
                    if v["target_id"] == ev["id"]
                ]
                if any(v["relation"] == "UNRELATED" for v in restrictions):
                    continue
                if any(v["relation"] == "UNKNOWN" for v in restrictions):
                    potential.append(ev["id"])
                    continue
                outcome = targets(ev["id"], "VERIFIES")[0]
                observed = targets(outcome["id"], "IN_CONTEXT")[0]["facts"]
                scope_keys = set(rule["scope"]) | {
                    pre["fact_key"]
                    for pre in targets(rule["id"], "REQUIRES")
                    if pre["mode"] == "necessary"
                }
                historical = {
                    k: [v["value"]]
                    for k, v in observed.items()
                    if k in scope_keys and v["availability"] == "KNOWN"
                }
                if set(historical) != scope_keys:
                    potential.append(ev["id"])
                    continue
                relation_to_context, _ = scope_relation(context, historical)
                if relation_to_context == "MATCH":
                    output.append(ev["id"])
                elif relation_to_context == "UNKNOWN":
                    potential.append(ev["id"])
    # Known exclusions and explicit governance precede evidence quantities.
    require(len(counter) <= 32, "CAPACITY_EXCEEDED")
    scope_checks = governance["scope_checks"]
    if any(v["relation"] == "UNRELATED" for v in scope_checks):
        verdict = "ABSTAIN"
        reasons = ["GOVERNANCE_SCOPE_RESTRICTED"]
    elif any(v["relation"] == "UNKNOWN" for v in scope_checks):
        reasons = ["GOVERNANCE_SCOPE_UNKNOWN"]
    elif conflicting:
        verdict = "ABSTAIN"
        reasons = ["HARD_PRECONDITION_VIOLATED"]
    elif not active and not governance["uncertain_records"]:
        verdict = "ABSTAIN"
        reasons = ["WITHDRAWN_EXPIRED_OR_OUTSIDE_SCOPE"]
    elif unknown:
        reasons = ["UNKNOWN_REQUIRED_OR_POTENTIAL_EVIDENCE"]
    elif (
        governance["integrity_issues"]
        or governance["uncertain_records"]
        or len(rules) != 1
    ):
        reasons = ["UNRESOLVED_REVISION_OR_SCOPE"]
    elif counter and support:
        reasons = ["CONFLICT"]
    elif counter:
        verdict = "ABSTAIN"
        reasons = ["AUTHORITATIVE_BUSINESS_COUNTEREXAMPLE"]
    elif unknown or potential:
        reasons = ["UNKNOWN_REQUIRED_OR_POTENTIAL_EVIDENCE"]
    elif not necessary or not support:
        reasons = ["NO_COMPLETE_APPLICABLE_SUPPORT"]
    else:
        verdict = "APPLY"
        reasons = ["COMPLETE_APPLICABLE_SUPPORT"]
    result = dict(
        contract_version="aevora.recommendation/2.0.0-rc2",
        recommendation_id=identity(
            nodes[witness["experience_id"]]["tenant_id"],
            "Recommendation",
            [
                query_id,
                witness["experience_id"],
                digest(witness),
                digest(facts),
                POLICY,
            ],
        ),
        query_id=query_id,
        experience_id=witness["experience_id"],
        revision_ids=active,
        core_verdict=verdict,
        reason_codes=reasons,
        policy_version=POLICY,
        semantic_epoch=witness["epoch"],
        authz_epoch=witness["authz_epoch"],
        context_sha256=digest(facts),
        witness_sha256=digest(witness),
        completeness="COMPLETE",
        required_fact_count=len(necessary),
        unknown_required=sorted(set(unknown)),
        integrity_issues=["GOVERNANCE_SELECTION_UNRESOLVED"]
        if governance["integrity_issues"] and active
        else [],
        contradiction_ids=sorted(counter),
        witness_refs=sorted(set(support + counter)),
        verification_steps=[
            "Independently establish unknown premises and test the actual artifact against its required engineering invariants."
        ]
        if verdict == "VERIFY"
        else [],
        attribution="UNKNOWN",
    )
    validate_schema("recommendation", result)
    return result
