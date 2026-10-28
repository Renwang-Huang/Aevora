package transfer

import (
	"bytes"
	"context"
	"database/sql"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"testing"
)

func TestTransferPreservesRawHistoryAndRejectsChangedData(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if e := platform.PrivateDir(root, true); e != nil {
		t.Fatal(e)
	}
	s, e := storage.Open(ctx, filepath.Join(root, "source.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	e = s.Write(ctx, func(r *storage.Repository) error {
		_, e := (domain.Service{Repo: domain.Repo{Repository: r}, Run: "source-run", Facts: Map{"worker_count": 1.0}}).ResolveExperience(ctx, Map{})
		return e
	})
	if e != nil {
		t.Fatal(e)
	}
	var nodes, edges bytes.Buffer
	e = s.Snapshot(ctx, func(r *storage.Repository) error {
		return r.WalkRaw(ctx, func(l, id string, raw []byte, sha string) error {
			b, e := codec.Canonical(Map{"label": l, "id": id, "payload_json": string(raw), "sha256": sha})
			nodes.Write(append(b, '\n'))
			return e
		}, func(v storage.Edge, raw []byte) error {
			b, e := codec.Canonical(Map{"id": v.ID, "relation": v.Relation, "source_label": v.SourceLabel, "source_id": v.SourceID, "target_label": v.TargetLabel, "target_id": v.TargetID, "payload_json": string(raw), "sha256": v.SHA256})
			edges.Write(append(b, '\n'))
			return e
		})
	})
	if e != nil {
		t.Fatal(e)
	}
	fingerprint, e := Fingerprint(ctx, s.Read(), "synthetic-source")
	if e != nil {
		t.Fatal(e)
	}
	result, e := (domain.Repo{Repository: s.Read()}).Resolve(ctx, Map{}, "2026-10-24T00:00:00+00:00", false)
	if e != nil {
		t.Fatal(e)
	}
	witnesses, e := codec.Canonical(Map{"cases": []any{Map{"context": Map{}, "as_of": "2026-10-24T00:00:00+00:00", "expected": result}}})
	if e != nil {
		t.Fatal(e)
	}
	input := filepath.Join(root, "export")
	if e = platform.PrivateDir(input, true); e != nil {
		t.Fatal(e)
	}
	refs := Map{}
	for name, raw := range map[string][]byte{"nodes.jsonl": nodes.Bytes(), "edges.jsonl": edges.Bytes(), "witnesses.json": witnesses} {
		p := filepath.Join(input, name)
		if e = platform.Exclusive(p, raw); e != nil {
			t.Fatal(e)
		}
		pin, e := storage.FileDigest(ctx, p)
		if e != nil {
			t.Fatal(e)
		}
		key := name[:len(name)-len(filepath.Ext(name))]
		refs[key] = Map{"path": name, "sha256": pin, "bytes": len(raw)}
	}
	manifest, e := codec.Canonical(Map{"schema_version": "aevora.logical-transfer/1", "logical_schema": storage.LogicalSchema, "query_version": storage.QueryVersion, "source_engine": "go-sqlite", "created_at": "2026-10-24T00:00:00+00:00", "counts": Map{"nodes": fingerprint["node_count"], "edges": fingerprint["edge_count"]}, "files": refs, "source_state": fingerprint, "capabilities_included": false})
	if e != nil {
		t.Fatal(e)
	}
	path := filepath.Join(input, "manifest.json")
	if e = platform.Exclusive(path, manifest); e != nil {
		t.Fatal(e)
	}
	pin, e := storage.FileDigest(ctx, path)
	if e != nil {
		t.Fatal(e)
	}
	receipt, e := Import(ctx, input, pin, filepath.Join(root, "import.db"))
	if e != nil || receipt["status"] != "VERIFIED" {
		t.Fatal(receipt, e)
	}
	backup := filepath.Join(root, "backup.db")
	if e = s.Backup(ctx, backup); e != nil {
		t.Fatal(e)
	}
	backupPin, e := storage.FileDigest(ctx, backup)
	if e != nil {
		t.Fatal(e)
	}
	receipt, e = Restore(ctx, backup, backupPin, filepath.Join(root, "restore.db"))
	if e != nil || receipt["status"] != "VERIFIED" {
		t.Fatal(receipt, e)
	}
	after, e := storage.FileDigest(ctx, backup)
	if e != nil || after != backupPin {
		t.Fatal("backup changed during restore", e)
	}
	if _, e = Restore(ctx, backup, backupPin, filepath.Join(root, "restore.db")); e == nil {
		t.Fatal("restore overwrote target")
	}
	if e = os.WriteFile(filepath.Join(input, "nodes.jsonl"), append(nodes.Bytes(), ' '), 0600); e != nil {
		t.Fatal(e)
	}
	if _, e = Import(ctx, input, pin, filepath.Join(root, "changed.db")); e == nil {
		t.Fatal("changed logical artifact accepted")
	}
	db, e := sql.Open("sqlite", backup)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec("CREATE TABLE unrecognized(value TEXT)"); e != nil {
		t.Fatal(e)
	}
	db.Close()
	changedPin, e := storage.FileDigest(ctx, backup)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = Restore(ctx, backup, changedPin, filepath.Join(root, "incompatible.db")); e == nil {
		t.Fatal("unrecognized actual schema accepted")
	}
}
