package storage

import (
	"context"
	"database/sql/driver"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"modernc.org/sqlite"
	"strings"
)

func init() {
	if err := sqlite.RegisterDeterministicScalarFunction("aevora_recall_terms", 1, func(_ *sqlite.FunctionContext, args []driver.Value) (driver.Value, error) {
		value, _ := args[0].(string)
		return strings.Join(retrieval.Terms(value), " "), nil
	}); err != nil {
		panic(err)
	}
}

// A connection-local, rebuildable projection. It never changes graph DDL,
// backups, immutable payloads or physical format. TEMP triggers participate in
// the source transaction: rolled-back proposals cannot survive in the index.
const recallDDL = `
CREATE VIRTUAL TABLE temp.aevora_recall USING fts5(
 id UNINDEXED, label UNINDEXED, title, summary, strategy,
 tokenize='porter unicode61'
);
CREATE TEMP TRIGGER aevora_recall_insert AFTER INSERT ON main.nodes
 WHEN new.label IN ('Experience','Candidate')
 BEGIN
 INSERT INTO aevora_recall(rowid,id,label,title,summary,strategy)
 SELECT new.rowid,new.id,new.label,
 aevora_recall_terms(coalesce(json_extract(new.payload,CASE new.label WHEN 'Candidate' THEN '$.body.title' ELSE '$.title' END),'')),
 aevora_recall_terms(coalesce(json_extract(new.payload,CASE new.label WHEN 'Candidate' THEN '$.body.public_summary' ELSE '$.public_summary' END),'')),
 aevora_recall_terms(coalesce(json_extract(new.payload,CASE new.label WHEN 'Candidate' THEN '$.body.strategy' ELSE '$.strategy' END),''));
 END;
INSERT INTO aevora_recall(rowid,id,label,title,summary,strategy)
 SELECT rowid,id,label,
 aevora_recall_terms(coalesce(json_extract(payload,CASE label WHEN 'Candidate' THEN '$.body.title' ELSE '$.title' END),'')),
 aevora_recall_terms(coalesce(json_extract(payload,CASE label WHEN 'Candidate' THEN '$.body.public_summary' ELSE '$.public_summary' END),'')),
 aevora_recall_terms(coalesce(json_extract(payload,CASE label WHEN 'Candidate' THEN '$.body.strategy' ELSE '$.strategy' END),''))
 FROM main.nodes WHERE label IN ('Experience','Candidate');
`

func ensureRecall(ctx context.Context, q queryer) error {
	var count int
	if err := q.QueryRowContext(ctx, "SELECT count(*) FROM sqlite_temp_schema WHERE name='aevora_recall'").Scan(&count); err != nil {
		return err
	}
	if count != 0 {
		return nil
	}
	if _, err := q.ExecContext(ctx, "SAVEPOINT aevora_recall_build"); err != nil {
		return err
	}
	if _, err := q.ExecContext(ctx, recallDDL); err != nil {
		q.ExecContext(context.Background(), "ROLLBACK TO aevora_recall_build; RELEASE aevora_recall_build")
		return err
	}
	_, err := q.ExecContext(ctx, "RELEASE aevora_recall_build")
	return err
}

type RecallHit struct {
	ID    string
	Score float64
}

// Recall scans an FTS index of public narratives only; source references and
// private evidence never contribute terms. Callers re-read and authorize each
// selected record before returning evidence. Scores express lexical rank only.
func (r *Repository) Recall(ctx context.Context, label, query string, limit, offset int) ([]RecallHit, []string, error) {
	if (label != "Experience" && label != "Candidate") || len(query) > 4000 || limit < 1 || limit > 100 || offset < 0 || offset > 10000 {
		return nil, nil, ErrInvalid
	}
	if err := r.chargeQuery(); err != nil {
		return nil, nil, err
	}
	match, expanded, _ := retrieval.Query(query)
	groups, minimum, _ := retrieval.Coverage(query)
	if match == "" {
		return []RecallHit{}, expanded, nil
	}
	q := r.q
	if !r.write {
		// TEMP indexes belong to the dedicated writer connection. Reader API
		// searches borrow it without changing main data or locking a read pool.
		conn, err := r.s.writer.Conn(ctx)
		if err != nil {
			return nil, nil, err
		}
		defer conn.Close()
		q = conn
	}
	if err := ensureRecall(ctx, q); err != nil {
		return nil, nil, err
	}
	coverage := ""
	args := []any{match, label}
	if minimum > 0 {
		votes := make([]string, len(groups))
		for i, group := range groups {
			votes[i] = `(CASE WHEN aevora_recall.rowid IN (SELECT rowid FROM aevora_recall WHERE aevora_recall MATCH ?) THEN 1 ELSE 0 END)`
			args = append(args, group)
		}
		coverage = " AND (" + strings.Join(votes, "+") + ") >= ?"
		args = append(args, minimum)
	}
	args = append(args, limit, offset)
	rows, err := q.QueryContext(ctx, `SELECT aevora_recall.id,bm25(aevora_recall,0,0,5.0,2.0,1.0)
 FROM aevora_recall JOIN main.nodes n ON n.rowid=aevora_recall.rowid
 WHERE aevora_recall MATCH ? AND aevora_recall.label=?
 AND (aevora_recall.label!='Experience' OR json_extract(n.payload,'$.publication_candidate_id') IS NULL OR EXISTS (
 SELECT 1 FROM main.nodes h WHERE h.label='LifecycleHead'
 AND json_extract(h.payload,'$.candidate_id')=json_extract(n.payload,'$.publication_candidate_id')
 AND json_extract(h.payload,'$.state')='PUBLISHED'))
 `+coverage+` ORDER BY bm25(aevora_recall,0,0,5.0,2.0,1.0),aevora_recall.id LIMIT ? OFFSET ?`, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	out := []RecallHit{}
	for rows.Next() {
		var hit RecallHit
		if err = rows.Scan(&hit.ID, &hit.Score); err != nil {
			return nil, nil, err
		}
		out = append(out, hit)
	}
	return out, expanded, rows.Err()
}
