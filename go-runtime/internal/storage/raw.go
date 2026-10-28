package storage

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
)

// WalkRaw runs against the caller's SQLite read transaction. The callback must
// not mutate it. Every stored byte/hash and derived edge identity is checked.
func (r *Repository) WalkRaw(ctx context.Context, node func(label, id string, raw []byte, sha string) error, edge func(Edge, []byte) error) error {
	rows, e := r.q.QueryContext(ctx, "SELECT label,id,payload,sha256 FROM nodes ORDER BY id")
	if e != nil {
		return e
	}
	for rows.Next() {
		var l, id, sha string
		var raw []byte
		if e = rows.Scan(&l, &id, &raw, &sha); e != nil {
			rows.Close()
			return e
		}
		p, e := decode(l, raw, sha)
		if e != nil {
			rows.Close()
			return e
		}
		canonical, e := codec.Canonical(p)
		if e != nil || string(canonical) != string(raw) || p["id"] != id {
			rows.Close()
			return ErrConflict
		}
		if e = node(l, id, raw, sha); e != nil {
			rows.Close()
			return e
		}
	}
	e = rows.Err()
	rows.Close()
	if e != nil {
		return e
	}
	rows, e = r.q.QueryContext(ctx, "SELECT id,relation,source_label,source_id,target_label,target_id,payload,sha256 FROM edges ORDER BY id")
	if e != nil {
		return e
	}
	defer rows.Close()
	for rows.Next() {
		var v Edge
		var raw []byte
		if e = rows.Scan(&v.ID, &v.Relation, &v.SourceLabel, &v.SourceID, &v.TargetLabel, &v.TargetID, &raw, &v.SHA256); e != nil {
			return e
		}
		v.Payload, e = decode("edge", raw, v.SHA256)
		if e != nil {
			return e
		}
		canonical, e := codec.Canonical(v.Payload)
		if e != nil || string(canonical) != string(raw) || v.Payload["id"] != v.ID || !AllowedRelation(v.Relation) || !AllowedLabel(v.SourceLabel) || !AllowedLabel(v.TargetLabel) {
			return ErrConflict
		}
		hash, e := codec.Digest([]any{v.Relation, v.SourceLabel, v.SourceID, v.TargetLabel, v.TargetID})
		if e != nil || v.ID != "edge:"+hash {
			return ErrConflict
		}
		if e = edge(v, raw); e != nil {
			return e
		}
	}
	return rows.Err()
}
