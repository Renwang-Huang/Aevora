package taskcapture

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestOfficialItemsProjectOnlyBoundedMetadata(t *testing.T) {
	raw := []byte(`{"method":"item/completed","params":{"threadId":"thread-a","turnId":"turn-a","item":{"id":"item-a","type":"commandExecution","command":"go test ./...","status":"failed","exitCode":1,"aggregatedOutput":"private marker /home/user/file secret-not-to-store"}}}`)
	e, err := Project(raw, "fixture", "repair")
	if err != nil || e["action"] != "GO_TEST" || e["status"] != "FAILED" {
		t.Fatal(e, err)
	}
	b, _ := json.Marshal(e)
	if strings.Contains(string(b), "secret-not-to-store") || strings.Contains(string(b), "/home/") {
		t.Fatal("raw output leaked")
	}
	ignored, err := Project([]byte(`{"method":"item/completed","params":{"item":{"type":"reasoning","content":"private"}}}`), "fixture", "repair")
	if err != nil || ignored != nil {
		t.Fatal(ignored, err)
	}
	root := filepath.Join(t.TempDir(), "private")
	platform.PrivateDir(root, true)
	if err = Enqueue(root, e); err != nil {
		t.Fatal(err)
	}
	if err = Enqueue(root, e); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 40; i++ {
		os.WriteFile(filepath.Join(folder(root), fmt.Sprintf("%064d.json", i)), []byte("bad"), 0600)
	}
	found := false
	for i := 0; i < 45; i++ {
		rows, _, err := Scan(root, 1)
		if err != nil {
			t.Fatal(err)
		}
		if len(rows) > 0 {
			found = true
			if err = Ack(rows[0]); err != nil {
				t.Fatal(err)
			}
			break
		}
	}
	if !found {
		t.Fatal("invalid records starved source")
	}
	// Only sanitized metadata reaches a real SQLite source record.
	db, err := storage.Open(context.Background(), filepath.Join(root, "db.sqlite"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err = db.Write(context.Background(), func(r *storage.Repository) error {
		_, e2 := (domain.Repo{Repository: r}).IngestTaskEvent(context.Background(), e)
		return e2
	}); err != nil {
		t.Fatal(err)
	}
}

func TestRuntimeDirectoryRoutingRejectsUnknownAndOtherWorkspaces(t *testing.T) {
	root := t.TempDir()
	r := NewRouter(root, "fixture", "repair")
	completed := []byte(`{"method":"item/completed","params":{"threadId":"thread-a","turnId":"turn-a","item":{"id":"item-a","type":"commandExecution","command":"go test ./...","status":"completed","exitCode":0}}}`)
	if e, err := r.Observe(completed); err != nil || e != nil {
		t.Fatal("unknown thread inherited project", e, err)
	}
	thread, _ := json.Marshal(domain.Map{"method": "thread/started", "params": domain.Map{"thread": domain.Map{"id": "thread-a", "cwd": root}}})
	r.Observe(thread)
	if e, err := r.Observe(completed); err != nil || e == nil {
		t.Fatal(e, err)
	}
	thread, _ = json.Marshal(domain.Map{"method": "thread/started", "params": domain.Map{"thread": domain.Map{"id": "thread-b", "cwd": t.TempDir()}}})
	r.Observe(thread)
	if e, err := r.Observe([]byte(strings.ReplaceAll(string(completed), "thread-a", "thread-b"))); err != nil || e != nil {
		t.Fatal("other workspace inherited project", e, err)
	}
}

func TestMalformedTypedCursorIsRetainedAndResetIsReversible(t *testing.T) {
	root := filepath.Join(t.TempDir(), "private")
	platform.PrivateDir(root, true)
	path := filepath.Join(root, "task-cursor.json")
	bad := []byte(`{"schema_version":"aevora.task-scan/1","last":42}`)
	os.WriteFile(path, bad, 0600)
	if _, _, e := Scan(root, 1); e == nil {
		t.Fatal("wrong cursor type silently reset")
	}
	actual, _ := os.ReadFile(path)
	if string(actual) != string(bad) {
		t.Fatal("bad cursor overwritten")
	}
	archive, e := ResetScan(root)
	if e != nil {
		t.Fatal(e)
	}
	actual, _ = os.ReadFile(archive)
	if string(actual) != string(bad) {
		t.Fatal("archive changed")
	}
	if _, _, e = Scan(root, 1); e != nil {
		t.Fatal(e)
	}
}
