package storage

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"os"
	"path/filepath"
	"testing"
)

func private(t *testing.T) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "owned")
	if e := os.Mkdir(p, 0700); e != nil {
		t.Fatal(e)
	}
	return p
}
func database(t *testing.T) *Store {
	t.Helper()
	s, e := Open(context.Background(), filepath.Join(private(t), "experience.db"), Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { s.Close() })
	return s
}
func TestImmutableTransactionAndForeignKeys(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	node := map[string]any{"id": "task:one", "public_title": "Unicode 中文"}
	if e := s.Write(ctx, func(r *Repository) error {
		if e := r.PutNode(ctx, "Task", node); e != nil {
			return e
		}
		return r.PutNode(ctx, "Task", node)
	}); e != nil {
		t.Fatal(e)
	}
	if e := s.Write(ctx, func(r *Repository) error {
		return r.PutNode(ctx, "Task", map[string]any{"id": "task:one", "public_title": "changed"})
	}); !errors.Is(e, ErrConflict) {
		t.Fatal(e)
	}
	e := s.Write(ctx, func(r *Repository) error {
		if e := r.PutNode(ctx, "Task", map[string]any{"id": "task:rollback"}); e != nil {
			return e
		}
		return r.PutEdge(ctx, "FOR_TASK", "Context", "context:absent", "Task", "task:rollback", nil)
	})
	if e == nil {
		t.Fatal("foreign key bypass")
	}
	p, e := s.Read().Get(ctx, "Task", "task:rollback")
	if e != nil || p != nil {
		t.Fatal("partial transaction", p, e)
	}
}
func TestFreshHeadEscapesReadSnapshot(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	old := map[string]any{"id": "head:a", "state": "PUBLISHED", "sequence": 0}
	if e := s.Write(ctx, func(r *Repository) error { return r.PutNode(ctx, "LifecycleHead", old) }); e != nil {
		t.Fatal(e)
	}
	hash, _ := codec.Digest(old)
	e := s.Snapshot(ctx, func(r *Repository) error {
		before, e := r.Get(ctx, "LifecycleHead", "head:a")
		if e != nil {
			return e
		}
		if e = s.Write(ctx, func(w *Repository) error {
			return w.CASHead(ctx, "head:a", hash, map[string]any{"id": "head:a", "state": "WITHDRAWN", "sequence": 1})
		}); e != nil {
			return e
		}
		stale, e := r.Get(ctx, "LifecycleHead", "head:a")
		if e != nil {
			return e
		}
		fresh, e := r.FreshHead(ctx, "head:a")
		if e != nil {
			return e
		}
		if before["state"] != "PUBLISHED" || stale["state"] != "PUBLISHED" || fresh["state"] != "WITHDRAWN" {
			t.Fatal("head snapshot incorrectly refreshed or reused")
		}
		return nil
	})
	if e != nil {
		t.Fatal(e)
	}
	if e = s.Write(ctx, func(r *Repository) error { return r.CASHead(ctx, "head:a", hash, old) }); !errors.Is(e, ErrConflict) {
		t.Fatal("stale CAS accepted", e)
	}
}
func TestBackupAndPhysicalOwnership(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	if _, e := Open(ctx, s.path, Options{}); e == nil {
		t.Fatal("second owner")
	}
	copy := filepath.Join(private(t), "backup.db")
	if e := s.Backup(ctx, copy); e != nil {
		t.Fatal(e)
	}
	restored, e := Open(ctx, copy, Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer restored.Close()
	a, _ := s.Identity()
	b, _ := restored.Identity()
	if a == b {
		t.Fatal("copied DB reused file identity")
	}
	p, e := restored.Read().Get(ctx, "Schema", LogicalSchema)
	if e != nil || p["version"] != LogicalSchema {
		t.Fatal(p, e)
	}
	if e = s.Backup(ctx, copy); e == nil {
		t.Fatal("backup overwrote target")
	}
}
func TestOpenFailsClosedWithoutCreatingAndRejectsLinks(t *testing.T) {
	root := private(t)
	path := filepath.Join(root, "missing.db")
	if _, e := Open(context.Background(), path, Options{}); e == nil {
		t.Fatal("missing DB accepted")
	}
	if _, e := os.Stat(path); !os.IsNotExist(e) {
		t.Fatal("missing database was created")
	}
	s, e := Open(context.Background(), path, Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	s.Close()
	alias := filepath.Join(root, "alias.db")
	if e = os.Link(path, alias); e != nil {
		t.Fatal(e)
	}
	if _, e = Open(context.Background(), alias, Options{}); e == nil {
		t.Fatal("hardlink alias accepted")
	}
	if e = os.Remove(alias); e != nil {
		t.Fatal(e)
	}
	if e = os.Symlink(path, alias); e != nil {
		t.Fatal(e)
	}
	if _, e = Open(context.Background(), alias, Options{}); e == nil {
		t.Fatal("symbolic alias accepted")
	}
}
func TestRunBindingCannotDrift(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	if e := s.BindRun(ctx, "run-a", "old", []byte(`{}`)); e != nil {
		t.Fatal(e)
	}
	if e := s.BindRun(ctx, "run-a", "new", []byte(`{}`)); !errors.Is(e, ErrConflict) {
		t.Fatal(e)
	}
}
