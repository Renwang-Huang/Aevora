package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"sort"
)

func (r Repo) targets(ctx context.Context, label, id, relation, target string) ([]Map, error) {
	edges, e := r.Edges(ctx, label, id, relation, false)
	if e != nil {
		return nil, e
	}
	out := []Map{}
	for _, edge := range edges {
		if edge.TargetLabel != target {
			continue
		}
		if e = r.RequireEdge(ctx, relation, label, id, target, edge.TargetID); e != nil {
			return nil, e
		}
		p, e := r.Required(ctx, target, edge.TargetID)
		if e != nil {
			return nil, e
		}
		out = append(out, p)
	}
	sort.Slice(out, func(i, j int) bool { return S(out[i]["id"]) < S(out[j]["id"]) })
	return out, nil
}
func (r Repo) PremisePaths(ctx context.Context, id string) ([]any, error) {
	revisions, e := r.targets(ctx, "Experience", id, "HAS_REVISION", "ExperienceRevision")
	if e != nil {
		return nil, e
	}
	out := []any{}
	for _, rev := range revisions {
		rules, e := r.targets(ctx, "ExperienceRevision", S(rev["id"]), "USES_RULE", "Rule")
		if e != nil {
			return nil, e
		}
		for _, rule := range rules {
			premises, e := r.targets(ctx, "Rule", S(rule["id"]), "REQUIRES", "Premise")
			if e != nil {
				return nil, e
			}
			for _, p := range premises {
				out = append(out, Map{"revision": storage.Public("ExperienceRevision", rev), "rule": storage.Public("Rule", rule), "premise": storage.Public("Premise", p), "path": []any{id, rev["id"], rule["id"], p["id"]}})
				if len(out) > 1200 {
					return nil, ErrInvalid
				}
			}
		}
	}
	return out, nil
}
func (r Repo) PublicPaths(ctx context.Context, id string) ([]any, error) {
	revisions, e := r.targets(ctx, "Experience", id, "HAS_REVISION", "ExperienceRevision")
	if e != nil {
		return nil, e
	}
	out := []any{}
	for _, rev := range revisions {
		revID := S(rev["id"])
		edges, e := r.Edges(ctx, "ExperienceRevision", revID, "", false)
		if e != nil {
			return nil, e
		}
		for _, edge := range edges {
			if edge.TargetLabel != "Evidence" || !stringSet("SUPPORTED_BY COUNTEREXAMPLE OBSERVED_OUTCOME")[edge.Relation] {
				continue
			}
			if e = r.RequireEdge(ctx, edge.Relation, "ExperienceRevision", revID, "Evidence", edge.TargetID); e != nil {
				return nil, e
			}
			ev, e := r.Required(ctx, "Evidence", edge.TargetID)
			if e != nil {
				return nil, e
			}
			outcomes, e := r.targets(ctx, "Evidence", edge.TargetID, "VERIFIES", "VerifiedOutcome")
			if e != nil {
				return nil, e
			}
			for _, o := range outcomes {
				contexts, e := r.targets(ctx, "VerifiedOutcome", S(o["id"]), "IN_CONTEXT", "Context")
				if e != nil {
					return nil, e
				}
				for _, c := range contexts {
					tasks, e := r.targets(ctx, "Context", S(c["id"]), "FOR_TASK", "Task")
					if e != nil {
						return nil, e
					}
					for _, task := range tasks {
						records := Map{"ExperienceRevision": storage.Public("ExperienceRevision", rev), "Evidence": storage.Public("Evidence", ev), "VerifiedOutcome": storage.Public("VerifiedOutcome", o), "Context": storage.Public("Context", c), "Task": storage.Public("Task", task)}
						out = append(out, Map{"relation": edge.Relation, "records": records, "path": []any{id, rev["id"], ev["id"], o["id"], c["id"], task["id"]}, "edge_types": []any{"HAS_REVISION", edge.Relation, "VERIFIES", "IN_CONTEXT", "FOR_TASK"}})
						if len(out) > 1200 {
							return nil, ErrInvalid
						}
					}
				}
			}
		}
	}
	sort.Slice(out, func(i, j int) bool {
		a, b := M(out[i]), M(out[j])
		ap, bp := A(a["path"]), A(b["path"])
		for k := 1; k < len(ap); k++ {
			if S(ap[k]) != S(bp[k]) {
				return S(ap[k]) < S(bp[k])
			}
		}
		return S(a["relation"]) < S(b["relation"])
	})
	return out, nil
}
func (r Repo) GovernanceView(ctx context.Context, id string) (Map, error) {
	revisions, e := r.targets(ctx, "Experience", id, "HAS_REVISION", "ExperienceRevision")
	if e != nil {
		return nil, e
	}
	if len(revisions) > 256 {
		return nil, ErrInvalid
	}
	rs, supersedes, events := []any{}, []any{}, []any{}
	targets := map[string]bool{}
	for _, record := range revisions {
		rules, e := r.targets(ctx, "ExperienceRevision", S(record["id"]), "USES_RULE", "Rule")
		if e != nil {
			return nil, e
		}
		ids := map[string]bool{}
		for _, rule := range rules {
			ids[S(rule["id"])] = true
		}
		complete := true
		if S(record["publication_audit_id"]) != "" {
			audit, e := r.Get(ctx, "AuditEvent", S(record["publication_audit_id"]))
			if e != nil {
				return nil, e
			}
			complete = audit != nil && audit["event"] == "rule_publication_complete" && audit["revision_id"] == record["id"] && audit["revision_sha256"] == H(record)
		}
		rs = append(rs, Map{"record": storage.Public("ExperienceRevision", record), "rule_ids": sortedSet(ids), "complete": complete})
		targets["ExperienceRevision\x00"+S(record["id"])] = true
		edges, e := r.Edges(ctx, "ExperienceRevision", S(record["id"]), "", false)
		if e != nil {
			return nil, e
		}
		for _, edge := range edges {
			if edge.Relation == "SUPERSEDES" && edge.TargetLabel == "ExperienceRevision" {
				if e = r.RequireEdge(ctx, "SUPERSEDES", edge.SourceLabel, edge.SourceID, edge.TargetLabel, edge.TargetID); e != nil {
					return nil, e
				}
				supersedes = append(supersedes, Map{"new_id": record["id"], "old_id": edge.TargetID, "edge_payload_sha256": edge.SHA256})
			}
			if edge.TargetLabel == "Evidence" && stringSet("SUPPORTED_BY COUNTEREXAMPLE OBSERVED_OUTCOME")[edge.Relation] {
				targets["Evidence\x00"+edge.TargetID] = true
			}
		}
	}
	sort.Slice(rs, func(i, j int) bool { return canonicalLess(M(rs[i])["record"], M(rs[j])["record"]) })
	sort.Slice(supersedes, func(i, j int) bool {
		a, b := M(supersedes[i]), M(supersedes[j])
		if a["new_id"] != b["new_id"] {
			return S(a["new_id"]) < S(b["new_id"])
		}
		return S(a["old_id"]) < S(b["old_id"])
	})
	rows, e := r.List(ctx, "GovernanceEvent", storage.Filter{Limit: 1025})
	if e != nil {
		return nil, e
	}
	if len(rows) > 1024 {
		return nil, ErrInvalid
	}
	sort.Slice(rows, func(i, j int) bool { return canonicalLess(rows[i], rows[j]) })
	for _, record := range rows {
		if !targets[S(record["target_label"])+"\x00"+S(record["target_id"])] {
			continue
		}
		audit, e := r.Get(ctx, "AuditEvent", S(record["completion_audit_id"]))
		if e != nil {
			return nil, e
		}
		complete := audit != nil && audit["event"] == "governance_event_complete" && audit["governance_event_id"] == record["id"] && audit["record_sha256"] == H(record)
		edges, e := r.Edges(ctx, "GovernanceEvent", S(record["id"]), "GOVERNS", false)
		if e != nil {
			return nil, e
		}
		present := len(edges) == 1 && edges[0].TargetLabel == record["target_label"] && edges[0].TargetID == record["target_id"]
		if present {
			e = r.RequireEdge(ctx, "GOVERNS", "GovernanceEvent", S(record["id"]), S(record["target_label"]), S(record["target_id"]))
			if e != nil {
				return nil, e
			}
		}
		events = append(events, Map{"record": storage.Public("GovernanceEvent", record), "complete": complete, "edge_present": present})
	}
	if len(events) > 256 || len(supersedes) > 1024 {
		return nil, ErrInvalid
	}
	return Map{"revisions": rs, "supersedes": supersedes, "events": events, "query_version": storage.QueryVersion, "consistency": "ACTUAL_MULTI_QUERY_RETRIEVAL; NOT_ATOMIC"}, nil
}
