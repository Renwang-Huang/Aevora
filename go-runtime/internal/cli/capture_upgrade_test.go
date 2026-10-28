package cli

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
)

func TestUpgradeReaderGuardChecksLogicalCaptureFormat(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind = "sqlite"
	p.Database.Path = filepath.Join(root, "db.sqlite")
	db, err := storage.Open(ctx, p.Database.Path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	db.Close()
	if err = checkCaptureReader(ctx, p, 0); err != nil {
		t.Fatal("empty/legacy database was blocked", err)
	}
	db, err = storage.Open(ctx, p.Database.Path, storage.Options{})
	if err != nil {
		t.Fatal(err)
	}
	event, err := captureformat.New("fixture", "session-1", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	err = db.Write(ctx, func(raw *storage.Repository) error {
		_, e := (domain.Repo{Repository: raw}).IngestCapture(ctx, event.Map())
		return e
	})
	db.Close()
	if err != nil {
		t.Fatal(err)
	}
	if err = checkCaptureReader(ctx, p, 0); err == nil || err.Error() != "AEVORA_UPGRADE_CAPTURE_RECORD_READER_REQUIRED" {
		t.Fatal("incompatible downgrade was permitted", err)
	}
	if err = checkCaptureReader(ctx, p, 2); err != nil {
		t.Fatal("compatible reader was blocked", err)
	}
	db, err = storage.Open(ctx, p.Database.Path, storage.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	n, err := db.Read().Count(ctx, "ExternalObservation", "")
	if err != nil || n != 1 {
		t.Fatal("guard rewrote capture data", n, err)
	}
}

func TestUpgradeRejectsOldTaskMemoryReadersWithoutChangingData(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	platform.PrivateDir(root, true)
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind = "sqlite"
	p.Database.Path = filepath.Join(root, "task.db")
	db, e := storage.Open(ctx, p.Database.Path, storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	event := domain.Map{"schema_version": domain.TaskEventVersion, "project": "fixture", "task_ref": "repair", "session_ref": "session-a", "turn_ref": "turn-a", "item_ref": "item-a", "kind": "CHECK", "status": "FAILED", "action": "CHECK", "summary": "Contract missing before the change", "exit_code": 1, "occurred_at": nil, "revision": nil}
	if e = db.Write(ctx, func(raw *storage.Repository) error {
		_, e := (domain.Repo{Repository: raw}).IngestTaskEvent(ctx, event)
		return e
	}); e != nil {
		t.Fatal(e)
	}
	db.Close()
	if e = checkTaskReader(ctx, p, 0); e == nil || e.Error() != "AEVORA_UPGRADE_TASK_MEMORY_READER_REQUIRED" {
		t.Fatal("incompatible rollback accepted", e)
	}
	if e = checkTaskReader(ctx, p, 1); e != nil {
		t.Fatal(e)
	}
	db, e = storage.Open(ctx, p.Database.Path, storage.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	if n, _ := db.Read().Count(ctx, "ExternalObservation", ""); n != 1 {
		t.Fatal("guard changed source data")
	}
}
