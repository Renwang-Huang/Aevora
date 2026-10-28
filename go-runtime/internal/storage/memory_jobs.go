package storage

import (
	"context"
	"strings"
)

func (r *Repository) AuditPrefix(ctx context.Context, prefix string, limit int, descending bool) ([]map[string]any, error) {
	if !strings.HasPrefix(prefix, "memory-job:") || len(prefix) > 160 || limit < 1 || limit > 128 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	order := "ASC"
	if descending {
		order = "DESC"
	}
	rows, e := r.q.QueryContext(ctx, `SELECT payload,sha256 FROM nodes WHERE label='AuditEvent' AND id>=? AND id<? ORDER BY id `+order+` LIMIT ?`, prefix, prefix+"\x7f", limit)
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
		p, e := decode("AuditEvent", raw, sha)
		if e != nil {
			return nil, e
		}
		if e = r.charge("AuditEvent", p["id"].(string), raw); e != nil {
			return nil, e
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (r *Repository) ReadyMemoryJobs(ctx context.Context, project string, limit int, now string) ([]map[string]any, error) {
	if !ValidID(project) || limit < 1 || limit > 16 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	rows, e := r.q.QueryContext(ctx, `SELECT n.payload,n.sha256 FROM nodes n WHERE n.label='AuditEvent' AND n.id>='memory-job:' AND n.id<'memory-job;'
 AND json_extract(n.payload,'$.project')=? AND json_extract(n.payload,'$.state') IN ('PENDING','RETRY','RUNNING')
 AND (json_extract(n.payload,'$.until') IS NULL OR julianday(json_extract(n.payload,'$.until'))<=julianday(?))
 AND NOT EXISTS(SELECT 1 FROM nodes newer WHERE newer.label='AuditEvent' AND newer.id>n.id AND newer.id<json_extract(n.payload,'$.job_id')||':~')
 ORDER BY n.id LIMIT ?`, project, now, limit)
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
		p, e := decode("AuditEvent", raw, sha)
		if e != nil {
			return nil, e
		}
		if e = r.charge("AuditEvent", p["id"].(string), raw); e != nil {
			return nil, e
		}
		out = append(out, p)
	}
	return out, rows.Err()
}
