package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
)

func TestCaptureCommitAndLostAcknowledgementAreIdempotent(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "graph.db")
	db, err := storage.Open(ctx, path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	e, err := captureformat.New("fixture", "session-1", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	var first Map
	write := func() (Map, error) {
		var out Map
		err := db.Write(ctx, func(raw *storage.Repository) error {
			var e2 error
			out, e2 = (Repo{raw}).IngestCapture(ctx, e.Map())
			return e2
		})
		return out, err
	}
	first, err = write()
	if err != nil || first["status"] != "RECORDED_UNTRUSTED" || first["outcome"] != "NOT_CREATED" {
		t.Fatal(first, err)
	}
	if err = db.Close(); err != nil {
		t.Fatal(err)
	}
	db, err = storage.Open(ctx, path, storage.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	retry, err := write()
	if err != nil || retry["status"] != "ALREADY_RECORDED_UNTRUSTED" || retry["observation_id"] != first["observation_id"] || retry["source_sha256"] != first["source_sha256"] {
		t.Fatal(retry, err)
	}
	rows, err := db.Read().List(ctx, "ExternalObservation", storage.Filter{Run: captureCurrentRun(e), Limit: 10})
	if err != nil || len(rows) != 1 {
		t.Fatal(rows, err)
	}
	outcomes, err := db.Read().List(ctx, "VerifiedOutcome", storage.Filter{Run: captureCurrentRun(e), Limit: 10})
	if err != nil || len(outcomes) != 0 {
		t.Fatal("capture became a verified result", outcomes, err)
	}
	invalid := e.Map()
	invalid["project"] = "another"
	err = db.Write(ctx, func(raw *storage.Repository) error { _, err := (Repo{raw}).IngestCapture(ctx, invalid); return err })
	if err == nil {
		t.Fatal("tampered event accepted")
	}
}
