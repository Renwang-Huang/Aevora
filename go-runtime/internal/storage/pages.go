package storage

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"strings"
)

type Header struct{ Label, ID string }
type PageFilter struct {
	Labels                 []string
	Run, Experience, After string
	Limit, Offset          int
	Timeline               bool
}

func placeholders(n int) string { return strings.TrimSuffix(strings.Repeat("?,", n), ",") }
func (r *Repository) Headers(ctx context.Context, f PageFilter) ([]Header, error) {
	if f.Limit < 1 || f.Limit > 101 || f.Offset < 0 || f.Offset > 1000 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	q := "SELECT n.label,n.id FROM nodes n WHERE n.label!='Schema' AND n.id>?"
	args := []any{f.After}
	if len(f.Labels) > 0 {
		for _, l := range f.Labels {
			if !AllowedLabel(l) {
				return nil, ErrInvalid
			}
			args = append(args, l)
		}
		q += " AND n.label IN (" + placeholders(len(f.Labels)) + ")"
	}
	if f.Run != "" {
		if !ValidID(f.Run) {
			return nil, ErrInvalid
		}
		if f.Timeline {
			q += " AND (json_extract(n.payload,'$.run_id')=? OR EXISTS(SELECT 1 FROM nodes c WHERE c.label='Candidate' AND c.id=json_extract(n.payload,'$.candidate_id') AND json_extract(c.payload,'$.run_id')=?))"
			args = append(args, f.Run, f.Run)
		} else {
			q += " AND json_extract(n.payload,'$.run_id')=?"
			args = append(args, f.Run)
		}
	}
	if f.Experience != "" {
		if !ValidID(f.Experience) {
			return nil, ErrInvalid
		}
		q += " AND EXISTS(SELECT 1 FROM edges e WHERE e.source_id=n.id AND e.target_label='Experience' AND e.target_id=? AND e.relation IN ('CONSIDERED','DECIDED'))"
		args = append(args, f.Experience)
	}
	q += " ORDER BY n.id LIMIT ? OFFSET ?"
	args = append(args, f.Limit, f.Offset)
	rows, e := r.q.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Header{}
	for rows.Next() {
		var h Header
		if e = rows.Scan(&h.Label, &h.ID); e != nil {
			return nil, e
		}
		if !AllowedLabel(h.Label) || !ValidID(h.ID) {
			return nil, ErrConflict
		}
		out = append(out, h)
	}
	return out, rows.Err()
}
func (r *Repository) AllCounts(ctx context.Context) (map[string]int, error) {
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	rows, e := r.q.QueryContext(ctx, "SELECT label,count(*) FROM nodes GROUP BY label LIMIT 32")
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := map[string]int{}
	for rows.Next() {
		var l string
		var n int
		if e = rows.Scan(&l, &n); e != nil {
			return nil, e
		}
		if !AllowedLabel(l) {
			return nil, ErrConflict
		}
		out[l] = n
	}
	return out, rows.Err()
}
func (r *Repository) Runs(ctx context.Context, after string, take int) ([]string, error) {
	if take < 1 || take > 1101 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	rows, e := r.q.QueryContext(ctx, "SELECT DISTINCT json_extract(payload,'$.run_id') AS run FROM nodes WHERE label IN ('Query','Decision','Candidate','VerifiedOutcome') AND json_extract(payload,'$.run_id')>? ORDER BY run LIMIT ?", after, take)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var id string
		if e = rows.Scan(&id); e != nil {
			return nil, e
		}
		if !ValidID(id) {
			return nil, ErrConflict
		}
		out = append(out, id)
	}
	return out, rows.Err()
}
func (r *Repository) RunCount(ctx context.Context) (int, error) {
	if e := r.chargeQuery(); e != nil {
		return 0, e
	}
	var n int
	e := r.q.QueryRowContext(ctx, "SELECT count(DISTINCT json_extract(payload,'$.run_id')) FROM nodes WHERE label IN ('Query','Decision','Candidate','VerifiedOutcome')").Scan(&n)
	return n, e
}
func (r *Repository) Neighbors(ctx context.Context, front, seen []string, run string, relations []string, take int) ([]Header, error) {
	if len(front) == 0 {
		return []Header{}, nil
	}
	if len(front) > 64 || len(seen) > 64 || take < 1 || take > 65 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	q := "SELECT DISTINCT n.label,n.id FROM nodes n JOIN (SELECT target_id AS id,relation FROM edges WHERE source_id IN (" + placeholders(len(front)) + ") UNION SELECT source_id AS id,relation FROM edges WHERE target_id IN (" + placeholders(len(front)) + ")) e ON e.id=n.id WHERE 1=1"
	args := []any{}
	for range 2 {
		for _, id := range front {
			args = append(args, id)
		}
	}
	if len(seen) > 0 {
		q += " AND n.id NOT IN (" + placeholders(len(seen)) + ")"
		for _, id := range seen {
			args = append(args, id)
		}
	}
	if run != "" {
		q += " AND (json_extract(n.payload,'$.run_id') IS NULL OR json_extract(n.payload,'$.run_id')=?)"
		args = append(args, run)
	}
	if len(relations) > 0 {
		for _, v := range relations {
			if !AllowedRelation(v) {
				return nil, ErrInvalid
			}
		}
		q += " AND e.relation IN (" + placeholders(len(relations)) + ")"
		for _, v := range relations {
			args = append(args, v)
		}
	}
	q += " ORDER BY n.id LIMIT ?"
	args = append(args, take)
	rows, e := r.q.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Header{}
	for rows.Next() {
		var h Header
		if e = rows.Scan(&h.Label, &h.ID); e != nil {
			return nil, e
		}
		if !AllowedLabel(h.Label) || !ValidID(h.ID) {
			return nil, ErrConflict
		}
		out = append(out, h)
	}
	return out, rows.Err()
}
func (r *Repository) Induced(ctx context.Context, ids []string, take int) ([]Edge, error) {
	if len(ids) == 0 {
		return []Edge{}, nil
	}
	if len(ids) > 64 || take < 1 || take > 1201 {
		return nil, ErrInvalid
	}
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	q := "SELECT id,relation,source_label,source_id,target_label,target_id,sha256 FROM edges WHERE source_id IN (" + placeholders(len(ids)) + ") AND target_id IN (" + placeholders(len(ids)) + ") ORDER BY source_id,id LIMIT ?"
	args := []any{}
	for range 2 {
		for _, id := range ids {
			args = append(args, id)
		}
	}
	args = append(args, take)
	rows, e := r.q.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, e
	}
	out := []Edge{}
	for rows.Next() {
		var v Edge
		if e = rows.Scan(&v.ID, &v.Relation, &v.SourceLabel, &v.SourceID, &v.TargetLabel, &v.TargetID, &v.SHA256); e != nil {
			rows.Close()
			return nil, e
		}
		out = append(out, v)
	}
	e = rows.Err()
	rows.Close()
	if e != nil {
		return nil, e
	}
	// Release the cursor before checked domain reads (also safe in one-reader tx).
	for _, v := range out {
		hash, err := codec.Digest([]any{v.Relation, v.SourceLabel, v.SourceID, v.TargetLabel, v.TargetID})
		if err != nil || v.ID != "edge:"+hash || !AllowedRelation(v.Relation) || !AllowedLabel(v.SourceLabel) || !AllowedLabel(v.TargetLabel) {
			return nil, ErrConflict
		}
		if e = r.RequireEdge(ctx, v.Relation, v.SourceLabel, v.SourceID, v.TargetLabel, v.TargetID); e != nil {
			return nil, e
		}
	}
	return out, nil
}
