package storage

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
)

// AvailableExperienceCount is inventory only. Reading a count does not grant
// applicability or bypass the checked lifecycle paths used for evidence.
func (r *Repository) AvailableExperienceCount(ctx context.Context) (int, error) {
	if err := r.chargeQuery(); err != nil {
		return 0, err
	}
	var n int
	err := r.q.QueryRowContext(ctx, `SELECT count(*) FROM nodes n WHERE label='Experience'
 AND (json_extract(payload,'$.publication_candidate_id') IS NULL OR EXISTS(
 SELECT 1 FROM nodes h WHERE h.label='LifecycleHead' AND json_extract(h.payload,'$.candidate_id')=json_extract(n.payload,'$.publication_candidate_id') AND json_extract(h.payload,'$.state')='PUBLISHED'))`).Scan(&n)
	return n, err
}

// RecallDocuments projects public narratives only. Vector generation happens
// after rows close, outside every write transaction. This is a bounded derived
// corpus, never evidence or publication authority.
func (r *Repository) RecallDocuments(ctx context.Context, label string, limit int) ([]retrieval.Document, bool, error) {
	if (label != "Experience" && label != "Candidate") || limit < 1 || limit > 4096 {
		return nil, false, ErrInvalid
	}
	if err := r.chargeQuery(); err != nil {
		return nil, false, err
	}
	rows, err := r.q.QueryContext(ctx, `SELECT id,
 substr(coalesce(json_extract(payload,CASE label WHEN 'Candidate' THEN '$.body.title' ELSE '$.title' END),''),1,200),
 substr(coalesce(json_extract(payload,CASE label WHEN 'Candidate' THEN '$.body.public_summary' ELSE '$.public_summary' END),''),1,600),
 substr(coalesce(json_extract(payload,CASE label WHEN 'Candidate' THEN '$.body.strategy' ELSE '$.strategy' END),''),1,1200)
 FROM nodes n WHERE label=? AND (label!='Experience' OR json_extract(payload,'$.publication_candidate_id') IS NULL OR EXISTS (
 SELECT 1 FROM nodes h WHERE h.label='LifecycleHead' AND json_extract(h.payload,'$.candidate_id')=json_extract(n.payload,'$.publication_candidate_id') AND json_extract(h.payload,'$.state')='PUBLISHED'))
 ORDER BY id LIMIT ?`, label, limit+1)
	if err != nil {
		return nil, false, err
	}
	defer rows.Close()
	out := []retrieval.Document{}
	more := false
	for rows.Next() {
		var id, title, summary, strategy string
		if err = rows.Scan(&id, &title, &summary, &strategy); err != nil {
			return nil, false, err
		}
		if len(out) == limit {
			more = true
			break
		}
		out = append(out, retrieval.Document{ID: id, Text: title + "\n" + summary + "\n" + strategy})
	}
	return out, more, rows.Err()
}

// Rerank only the bounded selected IDs, not a lexical-ID prefix of the entire
// corpus. Project only public narratives; never ship conditions or evidence.
func (r *Repository) RecallDocumentsByIDs(ctx context.Context, ids []string) ([]retrieval.Document, error) {
	if len(ids) > 64 {
		return nil, ErrInvalid
	}
	out := []retrieval.Document{}
	seen := map[string]bool{}
	for _, id := range ids {
		if !ValidID(id) || seen[id] {
			return nil, ErrInvalid
		}
		seen[id] = true
		if e := r.chargeQuery(); e != nil {
			return nil, e
		}
		rows, e := r.q.QueryContext(ctx, `SELECT
 substr(coalesce(json_extract(payload,'$.title'),''),1,200),
 substr(coalesce(json_extract(payload,'$.public_summary'),''),1,600),
 substr(coalesce(json_extract(payload,'$.strategy'),''),1,1200)
 FROM nodes n WHERE id=? AND label='Experience' AND (json_extract(payload,'$.publication_candidate_id') IS NULL OR EXISTS(
 SELECT 1 FROM nodes h WHERE h.label='LifecycleHead' AND json_extract(h.payload,'$.candidate_id')=json_extract(n.payload,'$.publication_candidate_id') AND json_extract(h.payload,'$.state')='PUBLISHED'))`, id)
		if e != nil {
			return nil, e
		}
		if rows.Next() {
			var title, summary, strategy string
			if e = rows.Scan(&title, &summary, &strategy); e != nil {
				rows.Close()
				return nil, e
			}
			out = append(out, retrieval.Document{ID: id, Text: title + "\n" + summary + "\n" + strategy})
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return nil, e
		}
	}
	return out, nil
}
