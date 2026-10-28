package storage

import (
	"context"
	"database/sql"
	"sync"
)

var expectedDDL struct {
	sync.Once
	rows [][4]string
	err  error
}

func ddl(ctx context.Context, q queryer) ([][4]string, error) {
	rows, e := q.QueryContext(ctx, "SELECT type,name,tbl_name,coalesce(sql,'') FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := [][4]string{}
	for rows.Next() {
		var v [4]string
		if e = rows.Scan(&v[0], &v[1], &v[2], &v[3]); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func checkDDL(ctx context.Context, q queryer) error {
	expectedDDL.Do(func() {
		db, e := sql.Open("sqlite", ":memory:")
		if e != nil {
			expectedDDL.err = e
			return
		}
		defer db.Close()
		db.SetMaxOpenConns(1)
		if _, e = db.ExecContext(context.Background(), schemaSQL); e != nil {
			expectedDDL.err = e
			return
		}
		expectedDDL.rows, expectedDDL.err = ddl(context.Background(), db)
	})
	if expectedDDL.err != nil {
		return expectedDDL.err
	}
	rows, e := ddl(ctx, q)
	if e != nil {
		return e
	}
	if len(rows) != len(expectedDDL.rows) {
		return ErrIncompatible
	}
	for i, v := range rows {
		if v != expectedDDL.rows[i] {
			return ErrIncompatible
		}
	}
	return nil
}
