package host_test

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/capture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestCaptureDrainsAfterRestartWithoutDuplicatingOrGrantingForeignProject(t *testing.T) {
	base := t.TempDir()
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(base, "registry"))
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	private := filepath.Join(base, "private")
	if err := platform.PrivateDir(private, true); err != nil {
		t.Fatal(err)
	}
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind, p.Database.Path = "sqlite", filepath.Join(private, "db.sqlite")
	p.Session.Root, p.Session.Facts = filepath.Join(private, "sessions"), json.RawMessage(`{}`)
	p.Console.Port = 17805
	db, err := storage.Open(ctx, p.Database.Path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	db.Close()
	if err = platform.PrivateDir(p.Session.Root, true); err != nil {
		t.Fatal(err)
	}
	workspace := filepath.Join(base, "workspace")
	if err = os.Mkdir(workspace, 0700); err != nil {
		t.Fatal(err)
	}
	pr := local.Project{Schema: "aevora.local-project/1", Name: "owned", Workspace: workspace, Profile: filepath.Join(private, "host.json"), BackendID: host.BackendID(p)}
	defer func() {
		dir := host.RegistryDir(pr.BackendID)
		for _, name := range []string{"management.json", "binding.json", "runtime.json"} {
			os.Remove(filepath.Join(dir, name))
		}
		os.Remove(dir)
	}()
	if err = local.Register(pr); err != nil {
		t.Fatal(err)
	}
	childPath := filepath.Join(base, "child")
	if err = os.Mkdir(childPath, 0700); err != nil {
		t.Fatal(err)
	}
	child := local.Project{Schema: "aevora.local-project/1", Name: "child", Workspace: childPath, Profile: pr.Profile, BackendID: pr.BackendID}
	if err = local.Register(child); err != nil {
		t.Fatal(err)
	}
	event, err := captureformat.New(pr.Name, "session-1", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	foreign, err := captureformat.New("foreign", "session-1", "turn-1", "call-2", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = capture.Enqueue(p.Session.Root, event); err != nil {
		t.Fatal(err)
	}
	if _, err = capture.Enqueue(p.Session.Root, foreign); err != nil {
		t.Fatal(err)
	}
	start := func() *host.Host {
		h, e := host.New(ctx, p, "control", false, native.Factory())
		if e != nil {
			t.Fatal(e)
		}
		if e = h.Ready("http://127.0.0.1:17805"); e != nil {
			t.Fatal(e)
		}
		go h.Serve(ctx)
		return h
	}
	h := start()
	result, err := host.ManagementCall(ctx, p, "", "configure-automatic", map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": true, "routes": []any{map[string]any{"project": child.Name, "workspace": child.Workspace}}})
	if err != nil || result["status"] != "COMPLETED" {
		t.Fatal(result, err)
	}
	wait := func(h *host.Host) {
		t.Helper()
		deadline := time.Now().Add(7 * time.Second)
		for time.Now().Before(deadline) {
			scan, e := capture.Scan(p.Session.Root, 10)
			if e == nil && scan.Pending == 1 && len(scan.Events) == 1 && scan.Events[0].ID == foreign.ID && h.Snapshot().Capture.Acknowledged > 0 {
				return
			}
			time.Sleep(50 * time.Millisecond)
		}
		t.Fatal("authorized record was not acknowledged or foreign record was lost", h.Snapshot().Capture)
	}
	wait(h)
	if err = h.Close(); err != nil {
		t.Fatal(err)
	}
	db, err = storage.Open(ctx, p.Database.Path, storage.Options{})
	if err != nil {
		t.Fatal(err)
	}
	count, err := db.Read().Count(ctx, "ExternalObservation", "")
	if err != nil || count != 1 {
		t.Fatal(count, err)
	}
	db.Close()
	// A repeated source event models a receiver commit followed by a lost ack.
	if _, err = capture.Enqueue(p.Session.Root, event); err != nil {
		t.Fatal(err)
	}
	h = start()
	wait(h)
	result, err = host.ManagementCall(ctx, p, "", "automatic-route", map[string]any{"project": child.Name, "apply": true})
	if err != nil || result["status"] != "COMPLETED" {
		t.Fatal("revoke failed", result, err)
	}
	revoked, err := captureformat.New(child.Name, "session-1", "turn-1", "call-3", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = capture.Enqueue(p.Session.Root, revoked); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(7 * time.Second)
	for time.Now().Before(deadline) && h.Snapshot().Capture.Unauthorized < 2 {
		time.Sleep(50 * time.Millisecond)
	}
	scan, err := capture.Scan(p.Session.Root, 10)
	if err != nil || scan.Pending != 2 || h.Snapshot().Capture.Unauthorized < 2 {
		t.Fatal("revoked source was not retained", scan, h.Snapshot().Capture, err)
	}
	if err = h.Close(); err != nil {
		t.Fatal(err)
	}
	db, err = storage.Open(ctx, p.Database.Path, storage.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	count, err = db.Read().Count(ctx, "ExternalObservation", "")
	if err != nil || count != 1 {
		t.Fatal("duplicate persisted after lost ack", count, err)
	}
}
