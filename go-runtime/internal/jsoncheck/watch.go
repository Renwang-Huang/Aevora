package jsoncheck

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
)

// Sweep advances one bounded page; after the end callers refresh from the start,
// allowing late IDs and changes to previously verified inputs to be observed.
func Sweep(ctx context.Context, p Plan, after string, invoke Invoke) (domain.Map, error) {
	if p.TaskRef == "" {
		return nil, domain.ErrInvalid
	}
	if _, e := invoke(ctx, "memory-process", domain.Map{"project": p.Project, "limit": 8}); e != nil {
		return nil, e
	}
	page, e := invoke(ctx, "memory-state", domain.Map{"project": p.Project, "after": after})
	if e != nil {
		return nil, e
	}
	seen := map[string]bool{}
	results := []any{}
	for _, value := range domain.A(page["jobs"]) {
		job := domain.M(value)
		candidate := domain.S(job["candidate_id"])
		if candidate == "" || seen[candidate] {
			continue
		}
		seen[candidate] = true
		info, e := invoke(ctx, "memory-source-info", domain.Map{"project": p.Project, "source_id": job["source_id"]})
		if e != nil {
			return nil, e
		}
		if domain.M(info["event"])["task_ref"] != p.TaskRef {
			continue
		}
		var result domain.Map
		if p.Unavailable {
			result, e = invoke(ctx, "memory-check-unavailable", domain.Map{"candidate_id": candidate, "project": p.Project})
		} else {
			result, e = Run(ctx, p, candidate, invoke)
		}
		if e != nil {
			retired, retireErr := invoke(ctx, "memory-check-unavailable", domain.Map{"candidate_id": candidate, "project": p.Project})
			if retireErr != nil {
				return nil, retireErr
			}
			results = append(results, domain.Map{"candidate_id": candidate, "status": "CHECK_FAILED_RETAINED", "support_state": retired["status"]})
			continue
		}
		results = append(results, result)
	}
	return domain.Map{"results": results, "next_cursor": page["next_cursor"], "more": page["more"], "scope": "CONFIGURED_JSON_CONTRACT_TASK_ONLY"}, nil
}
