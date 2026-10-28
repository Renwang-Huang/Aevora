package storage

import (
	"context"
	"database/sql"
	"errors"
)

func (r *Repository) IDs(ctx context.Context, label, after string, limit int) ([]string, error) {
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	if !AllowedLabel(label) || limit < 1 || limit > 4097 {
		return nil, ErrInvalid
	}
	rows, e := r.q.QueryContext(ctx, "SELECT id FROM nodes WHERE label=? AND id>? ORDER BY id LIMIT ?", label, after, limit)
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
		out = append(out, id)
	}
	return out, rows.Err()
}
func (r *Repository) Count(ctx context.Context, label, run string) (int, error) {
	if e := r.chargeQuery(); e != nil {
		return 0, e
	}
	if !AllowedLabel(label) {
		return 0, ErrInvalid
	}
	query := "SELECT count(*) FROM nodes WHERE label=?"
	args := []any{label}
	if run != "" {
		query += " AND json_extract(payload,'$.run_id')=?"
		args = append(args, run)
	}
	var n int
	e := r.q.QueryRowContext(ctx, query, args...).Scan(&n)
	return n, e
}
func (r *Repository) Operation(ctx context.Context, id, run, request string) ([]byte, bool, error) {
	var oldRun, oldRequest string
	var raw []byte
	e := r.q.QueryRowContext(ctx, "SELECT run_id,request_sha256,result FROM operation_results WHERE operation_id=?", id).Scan(&oldRun, &oldRequest, &raw)
	if errors.Is(e, sql.ErrNoRows) {
		return nil, false, nil
	}
	if e != nil {
		return nil, false, e
	}
	if oldRun != run || oldRequest != request {
		return nil, false, ErrConflict
	}
	return raw, true, nil
}
func (r *Repository) CompleteOperation(ctx context.Context, id, run, request string, result []byte) error {
	if !r.write || len(result) > 262144 {
		return ErrInvalid
	}
	_, e := r.q.ExecContext(ctx, "INSERT INTO operation_results VALUES(?,?,?,?)", id, run, request, result)
	return e
}

func (r *Repository) OperationInfo(ctx context.Context, id string) (map[string]any, error) {
	var run string
	var size int
	e := r.q.QueryRowContext(ctx, "SELECT run_id,length(result) FROM operation_results WHERE operation_id=?", id).Scan(&run, &size)
	if errors.Is(e, sql.ErrNoRows) {
		return map[string]any{"status": "NOT_FOUND", "operation_id": id}, nil
	}
	if e != nil {
		return nil, e
	}
	return map[string]any{"status": "COMMITTED", "operation_id": id, "run_id": run, "result_bytes": size, "response_delivery": "NOT_PROVEN_BY_DATABASE"}, nil
}
func (s *Store) Diagnostics(ctx context.Context) (map[string]any, error) {
	if e := s.check(); e != nil {
		return nil, e
	}
	var version, integrity string
	if e := s.readers.QueryRowContext(ctx, "SELECT sqlite_version()").Scan(&version); e != nil {
		return nil, e
	}
	if e := s.readers.QueryRowContext(ctx, "PRAGMA quick_check(1)").Scan(&integrity); e != nil {
		return nil, e
	}
	if integrity != "ok" {
		return nil, ErrConflict
	}
	rows, e := s.readers.QueryContext(ctx, "PRAGMA foreign_key_check")
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	if rows.Next() {
		return nil, ErrConflict
	}
	if e = rows.Err(); e != nil {
		return nil, e
	}
	return map[string]any{"database": "READY", "engine": "go-sqlite", "sqlite_version": version, "logical_schema": LogicalSchema, "storage_version": PhysicalVersion, "integrity": "ok", "foreign_keys": "ok", "ownership": "HELD", "mcp": "NOT_PROBED", "console": "NOT_PROBED", "runtime_ready": "NOT_PROVEN"}, nil
}
