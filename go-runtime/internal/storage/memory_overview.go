package storage

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"strings"
)

func (r *Repository) MemoryOverview(ctx context.Context, project string) (map[string]any, error) {
	return r.MemoryOverviewPage(ctx, project, "")
}
func (r *Repository) MemoryOverviewPage(ctx context.Context, project, after string) (map[string]any, error) {
	if (after != "" && !ValidID(after)) || (project != "" && !ValidID(project)) {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	where := `n.label='AuditEvent' AND n.id>='memory-job:' AND n.id<'memory-job;' AND (?='' OR json_extract(n.payload,'$.project')=?) AND NOT EXISTS(SELECT 1 FROM nodes newer WHERE newer.label='AuditEvent' AND newer.id>n.id AND newer.id<json_extract(n.payload,'$.job_id')||':~')`
	rows, e := r.q.QueryContext(ctx, `SELECT json_extract(n.payload,'$.state'),count(*) FROM nodes n WHERE `+where+` GROUP BY 1`, project, project)
	if e != nil {
		return nil, e
	}
	counts := map[string]any{}
	for rows.Next() {
		var state string
		var n int
		if e = rows.Scan(&state, &n); e != nil {
			rows.Close()
			return nil, e
		}
		counts[state] = n
	}
	if e = rows.Err(); e != nil {
		rows.Close()
		return nil, e
	}
	rows.Close()
	rows, e = r.q.QueryContext(ctx, `SELECT n.payload,n.sha256 FROM nodes n WHERE `+where+` AND n.id>? ORDER BY n.id LIMIT 21`, project, project, after)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	jobs := []any{}
	for rows.Next() {
		var raw []byte
		var sha string
		if e = rows.Scan(&raw, &sha); e != nil {
			return nil, e
		}
		p, e := decode("AuditEvent", raw, sha)
		if e != nil {
			return nil, e
		}
		jobs = append(jobs, map[string]any{"job_id": p["job_id"], "project": p["project"], "episode_id": p["run_id"], "state": p["state"], "reason": p["reason"], "attempts": p["attempts"], "candidate_id": p["candidate_id"], "source_id": p["source_id"], "cursor": p["id"]})
	}
	if e = rows.Err(); e != nil {
		return nil, e
	}
	rows.Close()
	for _, value := range jobs {
		job := value.(map[string]any)
		candidate, _ := job["candidate_id"].(string)
		if candidate == "" {
			continue
		}
		hash, e := codec.Digest(candidate)
		if e != nil {
			return nil, e
		}
		head, e := r.Get(ctx, "LifecycleHead", "candidate-head:"+hash)
		if e != nil || head == nil || head["candidate_id"] != candidate {
			return nil, ErrConflict
		}
		job["candidate_state"] = head["state"]
		links, e := r.Edges(ctx, "Candidate", candidate, "DERIVED_FROM", true)
		if e != nil {
			return nil, e
		}
		for _, link := range links {
			if link.SourceLabel != "Candidate" {
				continue
			}
			child, e := r.Get(ctx, "Candidate", link.SourceID)
			if e != nil {
				return nil, e
			}
			if child == nil || !strings.HasPrefix(child["id"].(string), "candidate:") {
				continue
			}
			if !strings.HasPrefix(stringMapField(child, "body", "candidate_key"), "json-contract-") {
				continue
			}
			h, e := codec.Digest(link.SourceID)
			if e != nil {
				return nil, e
			}
			verified, e := r.Get(ctx, "LifecycleHead", "candidate-head:"+h)
			if e != nil || verified == nil {
				return nil, ErrConflict
			}
			job["verified_candidate_state"] = verified["state"]
			job["verified_candidate_id"] = link.SourceID
			if verified["state"] == "PUBLISHED" {
				break
			}
		}

	}
	more := len(jobs) > 20
	next := ""
	if more {
		jobs = jobs[:20]
		next = jobs[19].(map[string]any)["cursor"].(string)
	}
	return map[string]any{"more": more, "next_cursor": next, "schema_version": "aevora.memory-overview/1", "states": counts, "jobs": jobs, "page_limit": 20, "ordering": "ID_NOT_RECENCY", "authority": "OPERATIONAL_STATE; NOT_ADOPTION_OR_CAUSAL_BENEFIT"}, rows.Err()
}

func stringMapField(p map[string]any, field, key string) string {
	m, _ := p[field].(map[string]any)
	v, _ := m[key].(string)
	return v
}
