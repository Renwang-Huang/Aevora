"""WHEN: compare graph-linked conditions and actual evidence with current public facts.

There is no Episode ID branch, strategy-specific if statement, or fallback corpus.
The process-lock and SQL cases use the same condition and path evaluation code.
"""
from __future__ import annotations

from .evidence_bundle import build_evidence_bundle
from .models import QUERY_VERSION, RULE_VERSION, canonical_json, digest, normalize_context, utc_now
from .governance import fact_state, project, SEMANTIC_SCOPE_KEYS, scope_relation as candidate_scope_relation
from .fact_catalog import support_coverage


def is_unknown(value) -> bool:
    return fact_state({"value": value}, "value") != "KNOWN"


def _equal(left, right) -> bool:
    # JSON distinguishes boolean from number; Python's True == 1 must not
    # accidentally validate worker/topology guarantees.
    return type(left) is type(right) and left == right


def _matches_allowed(value, allowed) -> bool:
    return any(_equal(value, item) for item in allowed)


def _context_relation(current: dict, historical: dict, keys: set[str]) -> tuple[str, list[str]]:
    """Compare factual contexts; unknown is potential relevance, never proved match."""
    unknown = []
    for key in sorted(keys):
        left, right = current.get(key), historical.get(key)
        if is_unknown(left) or is_unknown(right):
            unknown.append(key)
        elif not _equal(left, right):
            return "UNRELATED", []
    return ("UNKNOWN", unknown) if unknown else ("MATCH", [])


class ExperienceResolver:
    def __init__(self, repo):
        self.repo = repo

    def resolve(self, context: dict, *, as_of: str | None = None, persist_snapshots: bool = True) -> dict:
        context = normalize_context(context)
        as_of = as_of or utc_now()
        identifiers = self.repo.experience_ids()
        if len(identifiers) > 256:
            from .models import GraphError
            raise GraphError("Candidate bound exceeded before evidence retrieval")
        candidates = [self._resolve_one(context, build_evidence_bundle(self.repo, identifier), as_of)
                      for identifier in identifiers]
        for candidate in candidates:
            if persist_snapshots:
                # Exact response before this self-reference is immutable and replayable.
                receipt = self.repo.capture_query_snapshot({"context": context, "as_of": as_of,
                    "candidate": candidate, "query_version": QUERY_VERSION, "decision_engine_version": RULE_VERSION})
                candidate.update(query_snapshot_id=receipt["snapshot_id"], query_snapshot_sha256=receipt["snapshot_sha256"])
        # The evidence snapshot excludes Query/Decision nodes: a new query does
        # not itself masquerade as changed evidence or increased reliability.
        snapshot = {row["experience_id"]: row["retrieval_snapshot_sha256"] for row in candidates}
        return {"status": "AVAILABLE", "context": context, "candidates": candidates,
                "query_version": QUERY_VERSION, "decision_engine_version": RULE_VERSION,
                "graph_snapshot_sha256": digest(snapshot), "attribution": "UNKNOWN",
                "governance_evidence_sha256": digest({row["experience_id"]: row["governance_evidence_sha256"] for row in candidates}),
                "query_snapshot_ids": {row["experience_id"]: row.get("query_snapshot_id", "UNAVAILABLE") for row in candidates},
                "assurance": "Conditional principles from observed graph evidence; no success or causal guarantee"}

    def _resolve_one(self, context: dict, bundle: dict, as_of: str) -> dict:
        lifecycle=bundle.get('publication_lifecycle',{})
        if lifecycle and lifecycle.get('state')!='PUBLISHED':
            from .models import GraphError
            raise GraphError('Publication changed during non-atomic graph read; retry fresh retrieval')
        governance = project(bundle["governance"], context, as_of)
        premise_paths = [row for row in bundle["premise_paths"] if row["rule"]["id"] in governance["selected_rule_ids"]]
        rules = {row["rule"]["id"]: row["rule"] for row in premise_paths}
        premises = {row["premise"]["id"]: row["premise"] for row in premise_paths}
        errors = list(governance["integrity_issues"])
        if len(rules) != 1:
            errors.append("No complete uniquely selected graph rule")
        for rule in rules.values():
            declared = rule.get("premise_ids")
            reached = sorted({row["premise"]["id"] for row in premise_paths if row["rule"]["id"] == rule["id"]})
            if not isinstance(declared, list) or declared != reached or rule.get("premise_count") != len(reached):
                errors.append("Actual REQUIRES edges do not match the immutable rule declaration")
        if not premises:
            errors.append("No graph-linked applicability premises")
        matched, conflict, unknown = [], [], []
        for identifier, premise in sorted(premises.items()):
            key, allowed = premise["fact_key"], premise["allowed_values"]
            item = {"premise_id": identifier, "fact_key": key, "allowed_values": allowed,
                    "observed_value": context.get(key), "required": premise.get("required", True),
                    "observation_state": fact_state(context, key)}
            if is_unknown(context.get(key)):
                unknown.append(item)
            elif _matches_allowed(context[key], allowed):
                matched.append(item)
            else:
                conflict.append(item)
        required_conflicts = [p for p in conflict if p["required"]]
        required_unknown = [p for p in unknown if p["required"]]
        premise_keys = {p["fact_key"] for p in premises.values() if p.get("required", True)}
        # A matching predicate cannot extrapolate a one-process success into
        # every deployment. Current topology needs observed support coverage.
        coverage_keys = support_coverage(premise_keys)
        material_keys = set(governance["material_fact_keys"]) | (set(context) & SEMANTIC_SCOPE_KEYS)
        excluded = {(row["target_label"],row["target_id"]) for row in governance["excluded_targets"]}
        principal_support, missing_material, unrelated_paths, inactive_paths = [], [], [], []
        def path_scope(path):
            identifiers = {("Evidence",path["records"]["Evidence"]["id"]),
                           ("ExperienceRevision",path["records"]["ExperienceRevision"]["id"])}
            checks = [row for row in governance["path_scope_checks"] if (row["target_label"],row["target_id"]) in identifiers]
            relation = "UNRELATED" if any(row["relation"] == "UNRELATED" for row in checks) else (
                "UNKNOWN" if any(row["relation"] == "UNKNOWN" for row in checks) else "MATCH")
            return relation, sorted({key for row in checks for key in row["unknown_facts"]}), {
                key for row in checks for key in row["material_fact_keys"]}
        relevant_support, potential_support, invalid_support = [], [], []
        for path in bundle["support_paths"]:
            records = path["records"]
            historic = records["Context"].get("facts", {})
            if ("Evidence",records["Evidence"]["id"]) in excluded or ("ExperienceRevision",records["ExperienceRevision"]["id"]) in excluded:
                inactive_paths.append(path); continue
            scope_relation, scope_keys, path_material = path_scope(path)
            if scope_relation == "UNRELATED":
                unrelated_paths.append(path); continue
            if scope_relation == "UNKNOWN":
                potential_support.append({"path": path, "unknown_facts": scope_keys}); continue
            historically_supported = all(not is_unknown(historic.get(p["fact_key"]))
                                         and _matches_allowed(historic[p["fact_key"]], p["allowed_values"])
                                         for p in premises.values() if p.get("required", True))
            if records["VerifiedOutcome"].get("verdict") != "PASS" or not historically_supported:
                invalid_support.append(path["path"])
                continue
            relevance, keys = _context_relation(context, historic, coverage_keys)
            if relevance == "MATCH":
                principal_support.append(path)
                whole_relation, whole_keys = _context_relation(context, historic, coverage_keys | material_keys | path_material)
                if whole_relation == "MATCH":
                    relevant_support.append(path)
                elif whole_relation == "UNKNOWN":
                    potential_support.append({"path": path, "unknown_facts": whole_keys})
                    missing_material.extend({"fact_key": key, "current_state": fact_state(context, key),
                        "historical_state": fact_state(historic, key), "evidence_id": records["Evidence"]["id"]} for key in whole_keys)
                else:
                    unrelated_paths.append(path)
                    missing_material.extend({"fact_key": key, "current_state": fact_state(context, key),
                        "historical_state": fact_state(historic, key), "evidence_id": records["Evidence"]["id"],
                        "scope_relation": "UNKNOWN" if is_unknown(context.get(key)) or is_unknown(historic.get(key)) else "DIFFERENT"}
                        for key in sorted(material_keys | path_material)
                        if is_unknown(context.get(key)) or is_unknown(historic.get(key)) or not _equal(context[key], historic[key]))
            elif relevance == "UNKNOWN":
                potential_support.append({"path": path, "unknown_facts": keys})
        relevant_counter, potential_counter = [], []
        for path in bundle["counterexample_paths"]:
            records = path["records"]
            if ("Evidence",records["Evidence"]["id"]) in excluded or ("ExperienceRevision",records["ExperienceRevision"]["id"]) in excluded:
                inactive_paths.append(path); continue
            scope_relation, scope_keys, path_material = path_scope(path)
            if scope_relation == "UNRELATED":
                unrelated_paths.append(path); continue
            if scope_relation == "UNKNOWN":
                potential_counter.append({"path": path, "unknown_facts": scope_keys}); continue
            if records["VerifiedOutcome"].get("verdict") != "FAIL":
                continue
            historic = records["Context"].get("facts", {})
            # Include the recorded shared-state/failure domain, so a failure
            # from an unrelated datastore or symptom is not a universal veto.
            keys = coverage_keys | material_keys | path_material | (set(historic) & SEMANTIC_SCOPE_KEYS) | {
                key for key in ("shared_state_kind", "observed_failure_mode") if key in historic}
            relevance, unknown_keys = _context_relation(context, historic, keys)
            if relevance == "MATCH":
                relevant_counter.append(path)
            elif relevance == "UNKNOWN":
                potential_counter.append({"path": path, "unknown_facts": unknown_keys})
            else:
                unrelated_paths.append(path)
        evidence_conflicts = [{"support_path": positive["path"], "counterexample_path": negative["path"],
                              "classification": "SAME_APPLICABLE_SCOPE"}
                             for positive in relevant_support for negative in relevant_counter]
        scope_conflicts = [row for row in governance["scope_checks"] if row["relation"] == "UNRELATED"]
        scope_unknown = [row for row in governance["scope_checks"] if row["relation"] == "UNKNOWN"]
        if errors:
            decision, reason = "VERIFY", "INCOMPLETE_GRAPH_RULE"
        elif governance["uncertain_records"]:
            decision, reason = "VERIFY", "REVISION_OR_GOVERNANCE_SCOPE_UNKNOWN"
        elif scope_conflicts:
            decision, reason = "ABSTAIN", "CONFIRMED_GOVERNANCE_SCOPE_CONFLICT"
        elif scope_unknown:
            decision, reason = "VERIFY", "GOVERNANCE_SCOPE_FACTS_UNKNOWN"
        elif required_conflicts:
            decision = "ABSTAIN"
            reason = "PREMISE_CONFLICT_AND_MATCHING_COUNTEREXAMPLE" if relevant_counter else "CONFIRMED_PREMISE_CONFLICT"
        elif evidence_conflicts:
            decision, reason = "VERIFY", "CONFLICTING_VERIFIED_EVIDENCE"
        elif relevant_counter:
            decision, reason = "ABSTAIN", "MATCHING_VERIFIED_COUNTEREXAMPLE"
        elif required_unknown:
            decision, reason = "VERIFY", "REQUIRED_FACTS_UNKNOWN"
        elif potential_counter:
            decision, reason = "VERIFY", "POTENTIALLY_RELEVANT_COUNTEREXAMPLE_NEEDS_CONTEXT"
        elif not principal_support:
            decision, reason = "VERIFY", "NO_RELEVANT_COMPLETE_VERIFIED_SUPPORT"
        else:
            decision, reason = "APPLY", "PREMISES_MATCH_WITH_RELEVANT_VERIFIED_SUPPORT"
        principle_decision = decision
        if decision == "APPLY" and not relevant_support:
            decision, reason = "VERIFY", "CURRENT_OPERATION_SCOPE_NOT_COVERED"
        # These immutable proposal conditions are read through the actual
        # PUBLISHED_FROM/lifecycle graph path, not inferred from strategy text.
        lifecycle=bundle.get('publication_lifecycle',{})
        exclusions=lifecycle.get('inapplicable_conditions',{})
        exclusion_relation,exclusion_unknown=candidate_scope_relation(context,exclusions) if exclusions else ('UNRELATED',[])
        if exclusions and exclusion_relation=='MATCH':
            decision,reason='ABSTAIN','DECLARED_CANDIDATE_INAPPLICABILITY_MATCH'
        elif exclusions and exclusion_relation=='UNKNOWN' and decision!='ABSTAIN':
            decision,reason='VERIFY','DECLARED_CANDIDATE_INAPPLICABILITY_UNKNOWN'
            required_unknown.extend({'fact_key':key} for key in exclusion_unknown)
        if lifecycle:principle_decision=decision
        verification = ["Establish " + p["fact_key"] + " from the current public runtime, preserving unknown if unobservable"
                        for p in required_unknown]
        if decision == "VERIFY" and not verification:
            verification = (["Establish material fact " + key + " with independent evidence in the current operation"
                             for key in sorted({row["fact_key"] for row in missing_material})]
                            or ["Investigate missing graph relationship, competing evidence or obtain independent evidence in the current context"])
        return {"experience_id": bundle["experience_id"], "decision": decision, "reason": reason,
                "strategy": bundle["experience"].get("strategy"), "matched_premises": matched,
                "conflicting_premises": conflict, "unknown_premises": unknown,
                "graph_integrity_issues": errors, "relevant_support_paths": relevant_support,
                "principle_decision": principle_decision, "principle_support_paths": principal_support,
                "current_operation_coverage": "SUPPORTED_WITHIN_RECORDED_CONDITIONS" if decision == "APPLY" else "UNVERIFIED",
                "missing_material_premises": missing_material,
                "evidence_conflicts": evidence_conflicts, "unrelated_evidence_paths": unrelated_paths,
                "inactive_evidence_paths": inactive_paths, "governance_projection": governance,
                "missing_premises": [row for row in unknown if row["observation_state"] == "MISSING"],
                "not_observed_premises": [row for row in unknown if row["observation_state"] == "NOT_OBSERVED"],
                "potential_support_paths": potential_support, "invalid_support_paths": invalid_support,
                "relevant_counterexample_paths": relevant_counter, "potential_counterexample_paths": potential_counter,
                "verification_steps": verification, "evidence_bundle": bundle,
                "retrieval_snapshot_sha256": bundle["retrieval_snapshot_sha256"],
                "governance_evidence_sha256": bundle["governance_evidence_sha256"],
                "rule_ids": sorted(rules), "rule_versions": sorted({r.get("version", "UNAVAILABLE") for r in rules.values()}),
                "query_version": QUERY_VERSION, "decision_engine_version": RULE_VERSION,
                "recommendation_scope": "Conditional principle within evidenced premises; investigate the whole operation and do not copy a patch blindly",
                "attribution": "UNKNOWN"}
