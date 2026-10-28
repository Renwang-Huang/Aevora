package domain

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"sort"
	"strings"
)

func canonicalLess(a, b any) bool {
	x, _ := codec.Canonical(a)
	y, _ := codec.Canonical(b)
	return string(x) < string(y)
}
func Project(view, context Map, asOf string) (Map, error) {
	now, e := timestamp(asOf)
	if e != nil {
		return nil, e
	}
	revisions := map[string]Map{}
	for _, v := range A(view["revisions"]) {
		row := M(v)
		revisions[S(M(row["record"])["id"])] = row
	}
	errors := map[string]bool{}
	uncertain, inactive, active, pathScopes, uncertainEvents := []any{}, []any{}, []any{}, []any{}, []any{}
	material := map[string]bool{}
	excluded := map[string]bool{}
	adj := map[string][]string{}
	for _, v := range A(view["supersedes"]) {
		row := M(v)
		new, old := S(row["new_id"]), S(row["old_id"])
		adj[new] = append(adj[new], old)
		if revisions[new] == nil || revisions[old] == nil {
			errors["SUPERSEDES endpoint is outside this Experience"] = true
		}
	}
	colors := map[string]int{}
	var visit func(string, int)
	visit = func(node string, depth int) {
		if colors[node] == 1 {
			errors["SUPERSEDES contains a cycle"] = true
			return
		}
		if colors[node] == 2 {
			return
		}
		if depth >= 256 {
			errors["Revision traversal bound exceeded"] = true
			return
		}
		colors[node] = 1
		for _, old := range adj[node] {
			visit(old, depth+1)
		}
		colors[node] = 2
	}
	for node := range adj {
		visit(node, 0)
	}
	names := []string{}
	for id := range revisions {
		names = append(names, id)
	}
	sort.Strings(names)
	for _, id := range names {
		row := revisions[id]
		rev := M(row["record"])
		kind := S(rev["revision_kind"])
		if kind == "outcome_observation" || rev["revision_reason"] == "outcome_observed_no_attribution" {
			continue
		}
		legacy := kind == "" && rev["revision_reason"] == "initial_verified_history_import"
		if !legacy && kind != "rule_publication" {
			errors["Unclassified revision cannot publish an applicability rule"] = true
			continue
		}
		if !legacy {
			if !B(row["complete"]) {
				errors["Rule publication completion authority is missing"] = true
				continue
			}
			if !codec.Equal(row["rule_ids"], []any{rev["declared_rule_id"]}) {
				errors["USES_RULE does not match immutable publication declaration"] = true
			}
			declared, reached := map[string]bool{}, map[string]bool{}
			for _, v := range A(rev["supersedes_ids"]) {
				declared[S(v)] = true
			}
			for _, old := range adj[id] {
				reached[old] = true
			}
			if !codec.Equal(sortedSet(declared), sortedSet(reached)) {
				errors["SUPERSEDES does not match immutable publication declaration"] = true
			}
			start, e := timestamp(rev["valid_from"])
			if e != nil {
				return nil, e
			}
			if now.Before(start) {
				inactive = append(inactive, Map{"revision_id": id, "reason": "NOT_YET_EFFECTIVE"})
				continue
			}
			if rev["valid_until"] != nil {
				end, e := timestamp(rev["valid_until"])
				if e != nil {
					return nil, e
				}
				if !now.Before(end) {
					inactive = append(inactive, Map{"revision_id": id, "reason": "EXPIRED"})
					continue
				}
			}
			relation, unknown := ScopeRelation(context, M(rev["scope"]))
			if relation == "UNRELATED" {
				inactive = append(inactive, Map{"revision_id": id, "reason": "OUTSIDE_SCOPE"})
				continue
			}
			if relation == "UNKNOWN" {
				uncertain = append(uncertain, Map{"revision_id": id, "unknown_facts": unknown})
				continue
			}
		}
		if len(A(row["rule_ids"])) != 1 {
			errors["Revision does not have one complete rule association"] = true
		}
		active = append(active, id)
	}
	for _, v := range A(view["events"]) {
		row := M(v)
		event := M(row["record"])
		if !B(row["complete"]) || !B(row["edge_present"]) {
			errors["Governance declaration lacks its target or completion authority"] = true
			continue
		}
		at, e := timestamp(event["effective_at"])
		if e != nil {
			return nil, e
		}
		if now.Before(at) {
			continue
		}
		relation, unknown := ScopeRelation(context, M(event["scope"]))
		keys := map[string]bool{}
		for _, k := range A(event["material_fact_keys"]) {
			keys[S(k)] = true
		}
		for k := range M(event["scope"]) {
			keys[k] = true
		}
		check := Map{"event_id": event["id"], "target_id": event["target_id"], "target_label": event["target_label"], "relation": relation, "unknown_facts": unknown, "material_fact_keys": sortedSet(keys)}
		if event["event_type"] == "restrict_scope" {
			pathScopes = append(pathScopes, check)
		} else if relation == "UNKNOWN" {
			if event["target_label"] == "Evidence" {
				pathScopes = append(pathScopes, check)
			} else {
				uncertainEvents = append(uncertainEvents, check)
			}
		} else if relation == "MATCH" {
			excluded[S(event["target_label"])+"\x00"+S(event["target_id"])] = true
			inactive = append(inactive, Map{"target_id": event["target_id"], "target_label": event["target_label"], "event_id": event["id"], "reason": strings.ToUpper(S(event["event_type"]))})
		}
	}
	filtered := []any{}
	for _, id := range active {
		if !excluded["ExperienceRevision\x00"+S(id)] {
			filtered = append(filtered, id)
		}
	}
	active = filtered
	superseded, seen := map[string]bool{}, map[string]bool{}
	var predecessors func(string)
	predecessors = func(id string) {
		if seen[id] {
			return
		}
		seen[id] = true
		for _, old := range adj[id] {
			superseded[old] = true
			predecessors(old)
		}
	}
	for _, id := range active {
		predecessors(S(id))
	}
	activeSet := map[string]bool{}
	for _, id := range active {
		if !superseded[S(id)] {
			activeSet[S(id)] = true
		}
	}
	active = sortedSet(activeSet)
	filtered = []any{}
	for _, v := range uncertain {
		row := M(v)
		if !superseded[S(row["revision_id"])] {
			filtered = append(filtered, v)
		}
	}
	uncertain = filtered
	for _, v := range uncertainEvents {
		if activeSet[S(M(v)["target_id"])] {
			uncertain = append(uncertain, v)
		}
	}
	scopes := []any{}
	for _, v := range pathScopes {
		row := M(v)
		if row["target_label"] == "ExperienceRevision" && activeSet[S(row["target_id"])] {
			scopes = append(scopes, v)
			for _, k := range A(row["material_fact_keys"]) {
				material[S(k)] = true
			}
		}
	}
	rules := map[string]bool{}
	for _, id := range active {
		for _, rule := range A(revisions[S(id)]["rule_ids"]) {
			rules[S(rule)] = true
		}
	}
	if len(rules) != 1 {
		errors["No uniquely selected effective graph rule"] = true
	}
	targets, ids := []any{}, map[string]bool{}
	targetKeys := []string{}
	for k := range excluded {
		targetKeys = append(targetKeys, k)
	}
	sort.Strings(targetKeys)
	for _, key := range targetKeys {
		parts := strings.SplitN(key, "\x00", 2)
		targets = append(targets, Map{"target_label": parts[0], "target_id": parts[1]})
		ids[parts[1]] = true
	}
	return Map{"selected_revision_ids": active, "selected_rule_ids": sortedSet(rules), "superseded_revision_ids": sortedSet(superseded), "inactive_records": inactive, "uncertain_records": uncertain, "scope_checks": scopes, "path_scope_checks": pathScopes, "excluded_target_ids": sortedSet(ids), "excluded_targets": targets, "material_fact_keys": sortedSet(material), "integrity_issues": sortedSet(errors), "as_of": asOf, "selection_policy": "EXPLICIT_SUPERSEDES_AND_FACTUAL_SCOPE; NO_RECENCY_PRIORITY"}, nil
}
