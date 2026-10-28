package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"sort"
)

func (r Repo) ExperienceIDs(ctx context.Context) ([]string, error) {
	out := []string{}
	after := ""
	for {
		rows, e := r.IDs(ctx, "Experience", after, 256)
		if e != nil {
			return nil, e
		}
		for _, id := range rows {
			p, e := r.Required(ctx, "Experience", id)
			if e != nil {
				return nil, e
			}
			if candidate := S(p["publication_candidate_id"]); candidate != "" {
				yes, e := r.PublicationAllowed(ctx, candidate, id)
				if e != nil {
					return nil, e
				}
				if !yes {
					continue
				}
			}
			out = append(out, id)
			if len(out) > 256 {
				return nil, ErrInvalid
			}
		}
		if len(rows) < 256 {
			break
		}
		after = rows[len(rows)-1]
	}
	return out, nil
}
func (r Repo) Bundle(ctx context.Context, id string) (Map, error) {
	p, e := r.Get(ctx, "Experience", id)
	if e != nil {
		return nil, e
	}
	if p == nil {
		return Map{"status": "NOT_FOUND", "experience_id": id, "query_version": storage.QueryVersion, "paths": []any{}, "premise_paths": []any{}}, nil
	}
	experience := storage.Public("Experience", p)
	premises, e := r.PremisePaths(ctx, id)
	if e != nil {
		return nil, e
	}
	paths, e := r.PublicPaths(ctx, id)
	if e != nil {
		return nil, e
	}
	snapshot := Map{"experience": experience, "premise_paths": premises, "paths": paths}
	governance, e := r.GovernanceView(ctx, id)
	if e != nil {
		return nil, e
	}
	life := Map{}
	schema := "aevora.graph/1.1"
	if candidate := S(experience["publication_candidate_id"]); candidate != "" {
		view, e := r.Inspect(ctx, candidate)
		if e != nil {
			return nil, e
		}
		body := M(M(view["candidate"])["body"])
		events := []any{}
		for _, v := range A(view["events"]) {
			old := M(v)
			row := Map{}
			for _, k := range []string{"id", "from_state", "to_state", "created_at", "reason", "authority"} {
				if has(old, k) {
					row[k] = old[k]
				}
			}
			events = append(events, row)
		}
		l := Map{"candidate_id": candidate, "state": M(view["head"])["state"], "body_sha256": M(view["candidate"])["body_sha256"], "head_sha256": view["head_sha256"], "events": events, "causal_benefit": "UNKNOWN"}
		for _, k := range []string{"necessary_conditions", "inapplicable_conditions", "scope", "unknown_fields"} {
			l[k] = body[k]
		}
		life["publication_lifecycle"] = l
		schema = storage.LogicalSchema
	}
	support, counter, observed := []any{}, []any{}, []any{}
	revisions := map[string]bool{}
	for _, v := range paths {
		row := M(v)
		revisions[S(M(M(row["records"])["ExperienceRevision"])["id"])] = true
		switch row["relation"] {
		case "SUPPORTED_BY":
			support = append(support, v)
		case "COUNTEREXAMPLE":
			counter = append(counter, v)
		case "OBSERVED_OUTCOME":
			observed = append(observed, v)
		}
	}
	for _, v := range premises {
		revisions[S(M(M(v)["revision"])["id"])] = true
	}
	all := Map{"legacy_evidence": snapshot, "governance": governance}
	for k, v := range life {
		all[k] = v
	}
	out := Clone(snapshot)
	for k, v := range life {
		out[k] = v
	}
	for k, v := range (Map{"status": "AVAILABLE", "experience_id": id, "query_version": storage.QueryVersion, "schema_version": schema, "revision_ids": sortedSet(revisions), "support_paths": support, "counterexample_paths": counter, "observed_outcome_paths": observed, "retrieval_snapshot_sha256": H(snapshot), "governance": governance, "governance_evidence_sha256": H(all), "snapshot_assurance": "Actual bounded relationship-path retrieval; no distributed transaction assertion", "attribution": "UNKNOWN", "disclosure": "PUBLIC_ALLOWLIST_PROJECTION; no private report, suite identities or patch"}) {
		out[k] = v
	}
	return out, nil
}
func contextRelation(current, historic Map, keys map[string]bool) (string, []any) {
	unknown := []any{}
	for _, key := range sortedSet(keys) {
		k := S(key)
		if FactState(current, k) != "KNOWN" || FactState(historic, k) != "KNOWN" {
			unknown = append(unknown, k)
		} else if !codec.Equal(current[k], historic[k]) {
			return "UNRELATED", []any{}
		}
	}
	if len(unknown) > 0 {
		return "UNKNOWN", unknown
	}
	return "MATCH", unknown
}
func union(sets ...map[string]bool) map[string]bool {
	out := map[string]bool{}
	for _, set := range sets {
		for k, yes := range set {
			if yes {
				out[k] = true
			}
		}
	}
	return out
}
func required(p Map) bool { return !has(p, "required") || B(p["required"]) }
func pathScope(path, gov Map) (string, []any, map[string]bool) {
	records := M(path["records"])
	ids := map[string]bool{"Evidence\x00" + S(M(records["Evidence"])["id"]): true, "ExperienceRevision\x00" + S(M(records["ExperienceRevision"])["id"]): true}
	relation := "MATCH"
	unknown, material := map[string]bool{}, map[string]bool{}
	for _, v := range A(gov["path_scope_checks"]) {
		row := M(v)
		if !ids[S(row["target_label"])+"\x00"+S(row["target_id"])] {
			continue
		}
		if row["relation"] == "UNRELATED" {
			relation = "UNRELATED"
		} else if row["relation"] == "UNKNOWN" && relation != "UNRELATED" {
			relation = "UNKNOWN"
		}
		for _, k := range A(row["unknown_facts"]) {
			unknown[S(k)] = true
		}
		for _, k := range A(row["material_fact_keys"]) {
			material[S(k)] = true
		}
	}
	return relation, sortedSet(unknown), material
}

func ResolveOne(context, bundle Map, asOf string) (Map, error) {
	lifecycle := M(bundle["publication_lifecycle"])
	if len(lifecycle) > 0 && lifecycle["state"] != "PUBLISHED" {
		return nil, ErrConflict
	}
	gov, e := Project(M(bundle["governance"]), context, asOf)
	if e != nil {
		return nil, e
	}
	rules, premises := map[string]Map{}, map[string]Map{}
	selected := map[string]bool{}
	for _, v := range A(gov["selected_rule_ids"]) {
		selected[S(v)] = true
	}
	paths := []Map{}
	for _, v := range A(bundle["premise_paths"]) {
		row := M(v)
		rule := M(row["rule"])
		if selected[S(rule["id"])] {
			paths = append(paths, row)
			rules[S(rule["id"])] = rule
			p := M(row["premise"])
			premises[S(p["id"])] = p
		}
	}
	issues := append([]any{}, A(gov["integrity_issues"])...)
	if len(rules) != 1 {
		issues = append(issues, "No complete uniquely selected graph rule")
	}
	for _, rule := range rules {
		reached := map[string]bool{}
		for _, row := range paths {
			if M(row["rule"])["id"] == rule["id"] {
				reached[S(M(row["premise"])["id"])] = true
			}
		}
		if !codec.Equal(rule["premise_ids"], sortedSet(reached)) || !integer(rule["premise_count"]) || I(rule["premise_count"]) != len(reached) {
			issues = append(issues, "Actual REQUIRES edges do not match the immutable rule declaration")
		}
	}
	if len(premises) == 0 {
		issues = append(issues, "No graph-linked applicability premises")
	}
	matched, conflict, unknown := []any{}, []any{}, []any{}
	premiseKeys := map[string]bool{}
	pids := []string{}
	for id := range premises {
		pids = append(pids, id)
	}
	sort.Strings(pids)
	for _, id := range pids {
		p := premises[id]
		k := S(p["fact_key"])
		item := Map{"premise_id": id, "fact_key": k, "allowed_values": p["allowed_values"], "observed_value": context[k], "required": required(p), "observation_state": FactState(context, k)}
		if required(p) {
			premiseKeys[k] = true
		}
		if FactState(context, k) != "KNOWN" {
			unknown = append(unknown, item)
		} else if contains(p["allowed_values"], context[k]) {
			matched = append(matched, item)
		} else {
			conflict = append(conflict, item)
		}
	}
	requiredConflicts, requiredUnknown := []any{}, []any{}
	for _, v := range conflict {
		if B(M(v)["required"]) {
			requiredConflicts = append(requiredConflicts, v)
		}
	}
	for _, v := range unknown {
		if B(M(v)["required"]) {
			requiredUnknown = append(requiredUnknown, v)
		}
	}
	coverage := supportCoverage(premiseKeys)
	material := map[string]bool{}
	for _, k := range A(gov["material_fact_keys"]) {
		material[S(k)] = true
	}
	for k := range context {
		if semantic[k] {
			material[k] = true
		}
	}
	excluded := map[string]bool{}
	for _, v := range A(gov["excluded_targets"]) {
		row := M(v)
		excluded[S(row["target_label"])+"\x00"+S(row["target_id"])] = true
	}
	principal, missing, unrelated, inactive, relevantSupport, potentialSupport, invalidSupport := []any{}, []any{}, []any{}, []any{}, []any{}, []any{}, []any{}
	for _, v := range A(bundle["support_paths"]) {
		path := M(v)
		records := M(path["records"])
		ev := M(records["Evidence"])
		historic := M(M(records["Context"])["facts"])
		if excluded["Evidence\x00"+S(ev["id"])] || excluded["ExperienceRevision\x00"+S(M(records["ExperienceRevision"])["id"])] {
			inactive = append(inactive, v)
			continue
		}
		relation, scopeUnknown, pathMaterial := pathScope(path, gov)
		if relation == "UNRELATED" {
			unrelated = append(unrelated, v)
			continue
		}
		if relation == "UNKNOWN" {
			potentialSupport = append(potentialSupport, Map{"path": v, "unknown_facts": scopeUnknown})
			continue
		}
		supported := true
		for _, p := range premises {
			key := S(p["fact_key"])
			if required(p) && (FactState(historic, key) != "KNOWN" || !contains(p["allowed_values"], historic[key])) {
				supported = false
			}
		}
		if M(records["VerifiedOutcome"])["verdict"] != "PASS" || !supported {
			invalidSupport = append(invalidSupport, path["path"])
			continue
		}
		relation, unknownKeys := contextRelation(context, historic, coverage)
		if relation == "MATCH" {
			principal = append(principal, v)
			whole, wholeKeys := contextRelation(context, historic, union(coverage, material, pathMaterial))
			if whole == "MATCH" {
				relevantSupport = append(relevantSupport, v)
			} else if whole == "UNKNOWN" {
				potentialSupport = append(potentialSupport, Map{"path": v, "unknown_facts": wholeKeys})
				for _, key := range wholeKeys {
					k := S(key)
					missing = append(missing, Map{"fact_key": k, "current_state": FactState(context, k), "historical_state": FactState(historic, k), "evidence_id": ev["id"]})
				}
			} else {
				unrelated = append(unrelated, v)
				for _, key := range sortedSet(union(material, pathMaterial)) {
					k := S(key)
					if FactState(context, k) != "KNOWN" || FactState(historic, k) != "KNOWN" || !codec.Equal(context[k], historic[k]) {
						scope := "DIFFERENT"
						if FactState(context, k) != "KNOWN" || FactState(historic, k) != "KNOWN" {
							scope = "UNKNOWN"
						}
						missing = append(missing, Map{"fact_key": k, "current_state": FactState(context, k), "historical_state": FactState(historic, k), "evidence_id": ev["id"], "scope_relation": scope})
					}
				}
			}
		} else if relation == "UNKNOWN" {
			potentialSupport = append(potentialSupport, Map{"path": v, "unknown_facts": unknownKeys})
		}
	}
	relevantCounter, potentialCounter := []any{}, []any{}
	for _, v := range A(bundle["counterexample_paths"]) {
		path := M(v)
		records := M(path["records"])
		if excluded["Evidence\x00"+S(M(records["Evidence"])["id"])] || excluded["ExperienceRevision\x00"+S(M(records["ExperienceRevision"])["id"])] {
			inactive = append(inactive, v)
			continue
		}
		relation, scopeUnknown, pathMaterial := pathScope(path, gov)
		if relation == "UNRELATED" {
			unrelated = append(unrelated, v)
			continue
		}
		if relation == "UNKNOWN" {
			potentialCounter = append(potentialCounter, Map{"path": v, "unknown_facts": scopeUnknown})
			continue
		}
		if M(records["VerifiedOutcome"])["verdict"] != "FAIL" {
			continue
		}
		historic := M(M(records["Context"])["facts"])
		scopeKeys := union(coverage, material, pathMaterial)
		for k := range historic {
			if semantic[k] || k == "shared_state_kind" || k == "observed_failure_mode" {
				scopeKeys[k] = true
			}
		}
		relation, unknownKeys := contextRelation(context, historic, scopeKeys)
		if relation == "MATCH" {
			relevantCounter = append(relevantCounter, v)
		} else if relation == "UNKNOWN" {
			potentialCounter = append(potentialCounter, Map{"path": v, "unknown_facts": unknownKeys})
		} else {
			unrelated = append(unrelated, v)
		}
	}
	evidenceConflicts := []any{}
	for _, positive := range relevantSupport {
		for _, negative := range relevantCounter {
			evidenceConflicts = append(evidenceConflicts, Map{"support_path": M(positive)["path"], "counterexample_path": M(negative)["path"], "classification": "SAME_APPLICABLE_SCOPE"})
		}
	}
	scopeConflicts, scopeUnknown := 0, 0
	for _, v := range A(gov["scope_checks"]) {
		switch M(v)["relation"] {
		case "UNRELATED":
			scopeConflicts++
		case "UNKNOWN":
			scopeUnknown++
		}
	}
	decision, reason := "VERIFY", ""
	switch {
	case len(issues) > 0:
		reason = "INCOMPLETE_GRAPH_RULE"
	case len(A(gov["uncertain_records"])) > 0:
		reason = "REVISION_OR_GOVERNANCE_SCOPE_UNKNOWN"
	case scopeConflicts > 0:
		decision, reason = "ABSTAIN", "CONFIRMED_GOVERNANCE_SCOPE_CONFLICT"
	case scopeUnknown > 0:
		reason = "GOVERNANCE_SCOPE_FACTS_UNKNOWN"
	case len(requiredConflicts) > 0:
		decision, reason = "ABSTAIN", "CONFIRMED_PREMISE_CONFLICT"
		if len(relevantCounter) > 0 {
			reason = "PREMISE_CONFLICT_AND_MATCHING_COUNTEREXAMPLE"
		}
	case len(evidenceConflicts) > 0:
		reason = "CONFLICTING_VERIFIED_EVIDENCE"
	case len(relevantCounter) > 0:
		decision, reason = "ABSTAIN", "MATCHING_VERIFIED_COUNTEREXAMPLE"
	case len(requiredUnknown) > 0:
		reason = "REQUIRED_FACTS_UNKNOWN"
	case len(potentialCounter) > 0:
		reason = "POTENTIALLY_RELEVANT_COUNTEREXAMPLE_NEEDS_CONTEXT"
	case len(principal) == 0:
		reason = "NO_RELEVANT_COMPLETE_VERIFIED_SUPPORT"
	default:
		decision, reason = "APPLY", "PREMISES_MATCH_WITH_RELEVANT_VERIFIED_SUPPORT"
	}
	principle := decision
	if decision == "APPLY" && len(relevantSupport) == 0 {
		decision, reason = "VERIFY", "CURRENT_OPERATION_SCOPE_NOT_COVERED"
	}
	exclusions := M(lifecycle["inapplicable_conditions"])
	if len(exclusions) > 0 {
		relation, unknownKeys := ScopeRelation(context, exclusions)
		if relation == "MATCH" {
			decision, reason = "ABSTAIN", "DECLARED_CANDIDATE_INAPPLICABILITY_MATCH"
		} else if relation == "UNKNOWN" && decision != "ABSTAIN" {
			decision, reason = "VERIFY", "DECLARED_CANDIDATE_INAPPLICABILITY_UNKNOWN"
			for _, key := range unknownKeys {
				requiredUnknown = append(requiredUnknown, Map{"fact_key": key})
			}
		}
	}
	if len(lifecycle) > 0 {
		principle = decision
	}
	verification := []any{}
	for _, v := range requiredUnknown {
		verification = append(verification, "Establish "+S(M(v)["fact_key"])+" from the current public runtime, preserving unknown if unobservable")
	}
	if decision == "VERIFY" && len(verification) == 0 {
		missingKeys := map[string]bool{}
		for _, v := range missing {
			missingKeys[S(M(v)["fact_key"])] = true
		}
		for _, k := range sortedSet(missingKeys) {
			verification = append(verification, "Establish material fact "+S(k)+" with independent evidence in the current operation")
		}
		if len(verification) == 0 {
			verification = append(verification, "Investigate missing graph relationship, competing evidence or obtain independent evidence in the current context")
		}
	}
	missingPremises, notObserved := []any{}, []any{}
	for _, v := range unknown {
		if M(v)["observation_state"] == "MISSING" {
			missingPremises = append(missingPremises, v)
		}
		if M(v)["observation_state"] == "NOT_OBSERVED" {
			notObserved = append(notObserved, v)
		}
	}
	ruleIDs, versions := map[string]bool{}, map[string]bool{}
	for id, r := range rules {
		ruleIDs[id] = true
		versions[S(defaultValue(r, "version", "UNAVAILABLE"))] = true
	}
	coverageState := "UNVERIFIED"
	if decision == "APPLY" {
		coverageState = "SUPPORTED_WITHIN_RECORDED_CONDITIONS"
	}
	return Map{"experience_id": bundle["experience_id"], "decision": decision, "reason": reason, "strategy": M(bundle["experience"])["strategy"], "matched_premises": matched, "conflicting_premises": conflict, "unknown_premises": unknown, "graph_integrity_issues": issues, "relevant_support_paths": relevantSupport, "principle_decision": principle, "principle_support_paths": principal, "current_operation_coverage": coverageState, "missing_material_premises": missing, "evidence_conflicts": evidenceConflicts, "unrelated_evidence_paths": unrelated, "inactive_evidence_paths": inactive, "governance_projection": gov, "missing_premises": missingPremises, "not_observed_premises": notObserved, "potential_support_paths": potentialSupport, "invalid_support_paths": invalidSupport, "relevant_counterexample_paths": relevantCounter, "potential_counterexample_paths": potentialCounter, "verification_steps": verification, "evidence_bundle": bundle, "retrieval_snapshot_sha256": bundle["retrieval_snapshot_sha256"], "governance_evidence_sha256": bundle["governance_evidence_sha256"], "rule_ids": sortedSet(ruleIDs), "rule_versions": sortedSet(versions), "query_version": storage.QueryVersion, "decision_engine_version": RuleVersion, "recommendation_scope": "Conditional principle within evidenced premises; investigate the whole operation and do not copy a patch blindly", "attribution": "UNKNOWN"}, nil
}
func (r Repo) Resolve(ctx context.Context, facts Map, asOf string, persist bool) (Map, error) {
	if e := NormalizeContext(facts, false); e != nil {
		return nil, e
	}
	ids, e := r.ExperienceIDs(ctx)
	if e != nil {
		return nil, e
	}
	return r.resolveIDs(ctx, facts, asOf, persist, ids)
}

// Selected identities come from relevance recall, never caller-supplied IDs.
// Evidence and final publication/head checks remain in the original path.
func (r Repo) resolveIDs(ctx context.Context, facts Map, asOf string, persist bool, ids []string) (Map, error) {
	if e := NormalizeContext(facts, false); e != nil {
		return nil, e
	}
	candidates := []any{}
	snapshots, governance, querySnapshots := Map{}, Map{}, Map{}
	for _, id := range ids {
		bundle, e := r.Bundle(ctx, id)
		if e != nil {
			return nil, e
		}
		candidate, e := ResolveOne(facts, bundle, asOf)
		if e != nil {
			return nil, e
		}
		if persist {
			content := Map{"context": facts, "as_of": asOf, "candidate": candidate, "query_version": storage.QueryVersion, "decision_engine_version": RuleVersion}
			sha := H(content)
			if e = r.Put(ctx, "QuerySnapshot", Map{"id": "snapshot:" + sha, "content": content, "content_sha256": sha}); e != nil {
				return nil, e
			}
			candidate["query_snapshot_id"] = "snapshot:" + sha
			candidate["query_snapshot_sha256"] = sha
		}
		candidates = append(candidates, candidate)
		snapshots[id] = candidate["retrieval_snapshot_sha256"]
		governance[id] = candidate["governance_evidence_sha256"]
		querySnapshots[id] = defaultValue(candidate, "query_snapshot_id", "UNAVAILABLE")
	}
	return Map{"status": "AVAILABLE", "context": facts, "candidates": candidates, "query_version": storage.QueryVersion, "decision_engine_version": RuleVersion, "graph_snapshot_sha256": H(snapshots), "attribution": "UNKNOWN", "governance_evidence_sha256": H(governance), "query_snapshot_ids": querySnapshots, "assurance": "Conditional principles from observed graph evidence; no success or causal guarantee"}, nil
}
