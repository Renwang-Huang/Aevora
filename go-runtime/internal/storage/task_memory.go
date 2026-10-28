package storage

import (
	"context"
)

func (r *Repository) TaskSourceLinks(ctx context.Context, candidate, after string, limit int) ([]map[string]any, error) {
	if !ValidID(candidate) || (after != "" && !ValidID(after)) || limit < 1 || limit > 51 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	rows, e := r.q.QueryContext(ctx, `SELECT n.payload,n.sha256 FROM nodes n JOIN edges e ON e.target_id=n.id AND e.target_label=n.label WHERE e.source_label='Candidate' AND e.source_id=? AND e.relation='DERIVED_FROM' AND n.label='ExternalObservation' AND json_extract(n.payload,'$.record_kind')='ENGINEERING_TASK_EVENT' AND n.id>? ORDER BY n.id LIMIT ?`, candidate, after, limit)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var raw []byte
		var sha string
		if e = rows.Scan(&raw, &sha); e != nil {
			return nil, e
		}
		p, e := decode("ExternalObservation", raw, sha)
		if e != nil {
			return nil, e
		}
		if e = r.charge("ExternalObservation", p["id"].(string), raw); e != nil {
			return nil, e
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (r *Repository) HasTaskMemory(ctx context.Context) (bool, error) {
	if e := r.chargeQuery(); e != nil {
		return false, e
	}
	var exists int
	e := r.q.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM nodes WHERE (label='ExternalObservation' AND json_extract(payload,'$.record_kind')='ENGINEERING_TASK_EVENT') OR (label='AuditEvent' AND id>='memory-job:' AND id<'memory-job;'))`).Scan(&exists)
	return exists != 0, e
}
