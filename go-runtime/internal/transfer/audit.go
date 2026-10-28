// Package transfer implements explicit, offline migration into new projects.
package transfer

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
)

type Map = domain.Map

// Audit checks every raw record, all typed edges, lifecycle chains and immutable
// Query associations. It never regenerates or edits a historical QuerySnapshot.
func Audit(ctx context.Context, s *storage.Store, witnesses []any) (Map, error) {
	if _, e := s.Diagnostics(ctx); e != nil {
		return nil, e
	}
	repo := domain.Repo{Repository: s.Read()}
	if _, e := repo.Required(ctx, "Schema", storage.LogicalSchema); e != nil {
		return nil, e
	}
	counts := Map{}
	candidates, queries, decisions := []string{}, []string{}, []string{}
	nodes, edges := 0, 0
	e := s.Snapshot(ctx, func(r *storage.Repository) error {
		return r.WalkRaw(ctx, func(label, id string, raw []byte, sha string) error {
			nodes++
			if nodes > 100000 {
				return storage.ErrReadBudget
			}
			value, e := codec.Parse(raw)
			if e != nil {
				return e
			}
			if e = domain.ValidateRecord(label, domain.M(value)); e != nil {
				return e
			}
			if n, ok := counts[label].(int); ok {
				counts[label] = n + 1
			} else {
				counts[label] = 1
			}
			switch label {
			case "Candidate":
				candidates = append(candidates, id)
			case "Query":
				queries = append(queries, id)
			case "Decision":
				decisions = append(decisions, id)
			}
			return nil
		}, func(v storage.Edge, raw []byte) error {
			edges++
			if edges > 200000 {
				return storage.ErrReadBudget
			}
			return nil
		})
	})
	if e != nil {
		return nil, e
	}
	for _, id := range candidates {
		if _, e = repo.Inspect(ctx, id); e != nil {
			return nil, e
		}
	}
	legacyQueries, legacyDecisions := 0, 0
	for _, id := range queries {
		q, e := repo.Required(ctx, "Query", id)
		if e != nil {
			return nil, e
		}
		snapshots := domain.M(q["query_snapshot_ids"])
		if snapshots == nil {
			if q["query_version"] == storage.QueryVersion {
				return nil, domain.ErrConflict
			}
			legacyQueries++
			continue
		}
		ids := domain.A(q["candidate_experience_ids"])
		if len(ids) != len(snapshots) {
			return nil, domain.ErrConflict
		}
		for _, v := range ids {
			eid := domain.S(v)
			sid := domain.S(snapshots[eid])
			if !storage.ValidID(sid) {
				return nil, domain.ErrConflict
			}
			if e = repo.RequireEdge(ctx, "CONSIDERED", "Query", id, "Experience", eid); e != nil {
				return nil, e
			}
			if e = repo.RequireEdge(ctx, "AT_SNAPSHOT", "Query", id, "QuerySnapshot", sid); e != nil {
				return nil, e
			}
			snapshot, e := repo.Required(ctx, "QuerySnapshot", sid)
			if e != nil {
				return nil, e
			}
			content := domain.M(snapshot["content"])
			if domain.M(content["candidate"])["experience_id"] != eid || !codec.Equal(content["context"], q["task_context"]) {
				return nil, domain.ErrConflict
			}
		}
	}
	for _, id := range decisions {
		d, e := repo.Required(ctx, "Decision", id)
		if e != nil {
			return nil, e
		}
		if domain.S(d["query_id"]) == "" || domain.S(d["query_snapshot_id"]) == "" {
			legacyDecisions++
			continue
		}
		q, e := repo.Required(ctx, "Query", domain.S(d["query_id"]))
		if e != nil {
			return nil, e
		}
		eid := domain.S(d["experience_id"])
		if q["run_id"] != d["run_id"] || domain.M(q["query_snapshot_ids"])[eid] != d["query_snapshot_id"] {
			return nil, domain.ErrConflict
		}
		if e = repo.RequireEdge(ctx, "DECIDED", "Decision", id, "Experience", eid); e != nil {
			return nil, e
		}
	}
	if len(witnesses) > 32 {
		return nil, domain.ErrInvalid
	}
	for _, v := range witnesses {
		w := domain.M(v)
		facts := domain.M(w["context"])
		if len(w) != 3 || facts == nil {
			return nil, domain.ErrInvalid
		}
		if e = domain.NormalizeContext(facts, true); e != nil {
			return nil, e
		}
		result, e := repo.Resolve(ctx, facts, domain.S(w["as_of"]), false)
		if e != nil {
			return nil, e
		}
		if !codec.Equal(result, w["expected"]) {
			return nil, domain.ErrConflict
		}
	}
	return Map{"status": "VERIFIED", "nodes": nodes, "edges": edges, "labels": counts, "lifecycle_chains": len(candidates), "query_histories": len(queries) - legacyQueries, "decisions": len(decisions) - legacyDecisions, "legacy_query_histories_without_snapshots": legacyQueries, "legacy_decisions_without_snapshot_proof": legacyDecisions, "legacy_authority": "PRESERVED_RAW_HISTORY_ONLY; NOT_RECONSTRUCTED_OR_PROMOTED", "business_witnesses": len(witnesses), "historical_bytes": "PRESERVED", "capabilities": "REGENERATE_FOR_TARGET"}, nil
}
