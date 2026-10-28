package storage

import (
	"context"
	"strings"
)

// Physical SQLite compatibility does not imply that an older domain reader
// understands versioned capture assignments.
func (r *Repository) HasVersionedCapture(ctx context.Context) (bool, error) {
	if err := r.chargeQuery(); err != nil {
		return false, err
	}
	var exists int
	err := r.q.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM nodes WHERE label='ExternalObservation' AND json_extract(payload,'$.record_kind')='CODEX_DIAGNOSTIC_SIGNAL' AND (json_type(payload,'$.grouping') IS NOT NULL OR json_type(payload,'$.template_sha256') IS NOT NULL))`).Scan(&exists)
	return exists != 0, err
}

// ExternalByKind uses indexed run/candidate fields and a fixed kind. Typed
// capture events cannot crowd out unrelated usage reports in a bounded page.
func (r *Repository) ExternalByKind(ctx context.Context, candidate, run, kind string, limit int) ([]map[string]any, error) {
	return r.externalPage(ctx, candidate, run, kind, "", limit)
}
func (r *Repository) CaptureSourcePage(ctx context.Context, run, after string, limit int) ([]map[string]any, error) {
	return r.externalPage(ctx, "", run, "CODEX_DIAGNOSTIC_SIGNAL", after, limit)
}
func (r *Repository) externalPage(ctx context.Context, candidate, run, kind, after string, limit int) ([]map[string]any, error) {
	if (candidate == "" && run == "") || (candidate != "" && !ValidID(candidate)) || (run != "" && !ValidID(run)) ||
		(kind != "OBSERVATION_USE_CLAIM" && kind != "CODEX_DIAGNOSTIC_SIGNAL" && kind != "ENGINEERING_TASK_EVENT") || limit < 1 || limit > 128 || (after != "" && !ValidID(after)) {
		return nil, ErrInvalid
	}
	if err := r.chargeQuery(); err != nil {
		return nil, err
	}
	query := `SELECT CASE WHEN length(payload)<=262144 THEN payload ELSE null END,sha256 FROM nodes WHERE label='ExternalObservation' AND json_extract(payload,'$.record_kind')=?`
	args := []any{kind}
	if candidate != "" {
		query += ` AND json_extract(payload,'$.candidate_id')=?`
		args = append(args, candidate)
	}
	if run != "" {
		query += ` AND json_extract(payload,'$.run_id')=?`
		args = append(args, run)
	}
	if after != "" {
		query += ` AND id>?`
		args = append(args, after)
	}
	query += ` ORDER BY id LIMIT ?`
	args = append(args, limit)
	rows, err := r.q.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var raw []byte
		var sha string
		if err = rows.Scan(&raw, &sha); err != nil {
			return nil, err
		}
		if raw == nil {
			return nil, ErrReadBudget
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

func (r *Repository) CountExternalByKind(ctx context.Context, run, kind string) (int, error) {
	if !ValidID(run) || kind != "CODEX_DIAGNOSTIC_SIGNAL" {
		return 0, ErrInvalid
	}
	if err := r.chargeQuery(); err != nil {
		return 0, err
	}
	var n int
	err := r.q.QueryRowContext(ctx, `SELECT count(*) FROM nodes WHERE label='ExternalObservation' AND json_extract(payload,'$.run_id')=? AND json_extract(payload,'$.record_kind')=?`, run, kind).Scan(&n)
	return n, err
}

// Search only the three public narrative fields. Values are SQL parameters;
// private source references and arbitrary raw JSON never affect relevance.
func (r *Repository) SearchObservations(ctx context.Context, query string, limit int) ([]map[string]any, error) {
	if limit < 1 || limit > 20 || len(query) > 1000 {
		return nil, ErrInvalid
	}
	if err := r.chargeQuery(); err != nil {
		return nil, err
	}
	terms := strings.Fields(strings.ToLower(query))
	if len(terms) > 8 {
		return nil, ErrInvalid
	}
	text := `lower(coalesce(json_extract(payload,'$.body.title'),'') || ' ' || coalesce(json_extract(payload,'$.body.public_summary'),'') || ' ' || coalesce(json_extract(payload,'$.body.strategy'),''))`
	where := "label='Candidate'"
	args := []any{}
	if len(terms) > 0 {
		parts := []string{}
		for _, term := range terms {
			term = strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`).Replace(term)
			parts = append(parts, text+` LIKE ? ESCAPE '\'`)
			args = append(args, "%"+term+"%")
		}
		where += " AND (" + strings.Join(parts, " OR ") + ")"
	}
	args = append(args, limit)
	rows, err := r.q.QueryContext(ctx, "SELECT CASE WHEN length(payload)<=262144 THEN payload ELSE null END,sha256 FROM nodes WHERE "+where+" ORDER BY json_extract(payload,'$.created_at') DESC,id LIMIT ?", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var raw []byte
		var sha string
		if err = rows.Scan(&raw, &sha); err != nil {
			return nil, err
		}
		if raw == nil {
			return nil, ErrReadBudget
		}
		p, err := decode("Candidate", raw, sha)
		if err != nil {
			return nil, err
		}
		if err = r.charge("Candidate", p["id"].(string), raw); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}
