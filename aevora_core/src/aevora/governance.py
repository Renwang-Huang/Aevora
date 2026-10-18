"""Pure projection of actual append-only graph records. No strategy/episode table."""
from __future__ import annotations

from .models import InvalidRecord, parse_timestamp

SEMANTIC_SCOPE_KEYS = frozenset({"operation_semantics", "authority_model", "authority_validation",
    "clock_domain", "failure_domain", "contract_version", "lease_expiry_semantics", "supported_operation_set",
    "observed_failure_mode"})


def fact_state(context: dict, key: str) -> str:
    if key not in context:
        return "MISSING"
    value = context[key]
    if isinstance(value, str) and value.strip().lower().replace("-", "_").replace(" ", "_") == "not_observed":
        return "NOT_OBSERVED"
    if value is None or (isinstance(value, str) and value.strip().lower() in {"unknown", "unavailable", "unspecified"}):
        return "UNKNOWN"
    return "KNOWN"


def equal(left, right) -> bool:
    return type(left) is type(right) and left == right


def scope_relation(context: dict, scope: dict) -> tuple[str, list[str]]:
    unknown = []
    for key, allowed in sorted(scope.items()):
        if fact_state(context, key) != "KNOWN":
            unknown.append(key)
        elif not any(equal(context[key], value) for value in allowed):
            return "UNRELATED", []
    return ("UNKNOWN", unknown) if unknown else ("MATCH", [])


def project(view: dict, context: dict, as_of: str) -> dict:
    """Publication order is explicit SUPERSEDES; timestamps only bound validity."""
    now = parse_timestamp(as_of)
    revisions = {row["record"]["id"]: row for row in view["revisions"]}
    errors, uncertain, inactive, active = [], [], [], []
    scopes, path_scopes, uncertain_events, material_keys, excluded = [], [], [], set(), set()
    edge_pairs = {(row["new_id"], row["old_id"]) for row in view["supersedes"]}
    adjacency = {}
    for new, old in edge_pairs:
        adjacency.setdefault(new, []).append(old)
        if new not in revisions or old not in revisions:
            errors.append("SUPERSEDES endpoint is outside this Experience")
    colors = {}
    def visit(node, depth=0):
        if colors.get(node) == 1:
            errors.append("SUPERSEDES contains a cycle")
            return
        if colors.get(node) == 2:
            return
        if depth >= 256:
            errors.append("Revision traversal bound exceeded")
            return
        colors[node] = 1
        for old in adjacency.get(node, []):
            visit(old, depth + 1)
        colors[node] = 2
    for node in adjacency:
        visit(node)
    for identifier, row in sorted(revisions.items()):
        revision = row["record"]
        kind = revision.get("revision_kind")
        if kind == "outcome_observation" or revision.get("revision_reason") == "outcome_observed_no_attribution":
            continue
        legacy = kind is None and revision.get("revision_reason") == "initial_verified_history_import"
        if not legacy and kind != "rule_publication":
            errors.append("Unclassified revision cannot publish an applicability rule")
            continue
        if not legacy:
            if not row["complete"]:
                errors.append("Rule publication completion authority is missing")
                continue
            if row["rule_ids"] != [revision["declared_rule_id"]]:
                errors.append("USES_RULE does not match immutable publication declaration")
            declared = set(revision["supersedes_ids"])
            reached = {old for new, old in edge_pairs if new == identifier}
            if reached != declared:
                errors.append("SUPERSEDES does not match immutable publication declaration")
            if now < parse_timestamp(revision["valid_from"]):
                inactive.append({"revision_id": identifier, "reason": "NOT_YET_EFFECTIVE"}); continue
            if revision.get("valid_until") and now >= parse_timestamp(revision["valid_until"]):
                inactive.append({"revision_id": identifier, "reason": "EXPIRED"}); continue
            relation, keys = scope_relation(context, revision.get("scope", {}))
            if relation == "UNRELATED":
                inactive.append({"revision_id": identifier, "reason": "OUTSIDE_SCOPE"}); continue
            if relation == "UNKNOWN":
                uncertain.append({"revision_id": identifier, "unknown_facts": keys}); continue
        if len(row["rule_ids"]) != 1:
            errors.append("Revision does not have one complete rule association")
        active.append(identifier)
    for event_row in view["events"]:
        event = event_row["record"]
        if not event_row["complete"] or not event_row["edge_present"]:
            errors.append("Governance declaration lacks its target or completion authority")
            continue
        if now < parse_timestamp(event["effective_at"]):
            continue
        if event["event_type"] == "restrict_scope":
            relation, keys = scope_relation(context, event.get("scope", {}))
            path_scopes.append({"event_id": event["id"], "target_id": event["target_id"],
                "target_label": event["target_label"], "relation": relation, "unknown_facts": keys,
                "material_fact_keys": sorted(set(event.get("material_fact_keys", [])) | set(event.get("scope", {})))})
        else:
            relation, keys = scope_relation(context, event.get("scope", {}))
            if relation == "UNKNOWN":
                row = {"event_id": event["id"], "target_id": event["target_id"],
                    "target_label": event["target_label"], "relation": relation, "unknown_facts": keys,
                    "material_fact_keys": sorted(set(event.get("material_fact_keys", [])) | set(event.get("scope", {})))}
                if event["target_label"] == "Evidence":
                    path_scopes.append(row)
                else:
                    uncertain_events.append(row)
            elif relation == "MATCH":
                excluded.add((event["target_label"], event["target_id"]))
                inactive.append({"target_id": event["target_id"], "target_label": event["target_label"],
                    "event_id": event["id"], "reason": event["event_type"].upper()})
    active = [identifier for identifier in active if ("ExperienceRevision",identifier) not in excluded]
    # A scoped successor removes its predecessors only where that successor
    # really applies; this is not a latest-timestamp winner.
    superseded = set()
    traversed = set()
    def predecessors(identifier):
        if identifier in traversed:
            return
        traversed.add(identifier)
        for old in adjacency.get(identifier, []):
            superseded.add(old); predecessors(old)
    for identifier in active:
        predecessors(identifier)
    active = sorted(set(active) - superseded)
    uncertain = [row for row in uncertain if row.get("revision_id") not in superseded]
    uncertain.extend(row for row in uncertain_events if row["target_id"] in active)
    scopes = [row for row in path_scopes if row["target_label"] == "ExperienceRevision" and row["target_id"] in active]
    for row in scopes:
        material_keys.update(row["material_fact_keys"])
    rules = sorted({rule for identifier in active for rule in revisions[identifier]["rule_ids"]})
    if len(rules) != 1:
        errors.append("No uniquely selected effective graph rule")
    return {"selected_revision_ids": active, "selected_rule_ids": rules,
            "superseded_revision_ids": sorted(superseded), "inactive_records": inactive,
            "uncertain_records": uncertain, "scope_checks": scopes,
            "path_scope_checks": path_scopes,
            "excluded_target_ids": sorted({identifier for _,identifier in excluded}),
            "excluded_targets": [{"target_label":label,"target_id":identifier} for label,identifier in sorted(excluded)],
            "material_fact_keys": sorted(material_keys),
            "integrity_issues": sorted(set(errors)), "as_of": as_of,
            "selection_policy": "EXPLICIT_SUPERSEDES_AND_FACTUAL_SCOPE; NO_RECENCY_PRIORITY"}
