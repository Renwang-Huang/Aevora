package native

import (
	"context"
	"database/sql"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
)

func TestIdleInternalMaintenanceDoesNotAppendOperationReceipts(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	platform.PrivateDir(root, true)
	path := filepath.Join(root, "db.sqlite")
	store, e := storage.Open(ctx, path, storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	r, e := New(ctx, store, engine.RunContext{BackendID: "owned", WorkspaceID: "workspace", RunID: "maintenance", Facts: json.RawMessage(`{}`), FactsVersion: "public-context/1", FactsSource: "protected_host_profile"})
	if e != nil {
		t.Fatal(e)
	}
	defer r.Close()
	for i := 0; i < 100; i++ {
		v, handled, e := r.ReadMaintenance(ctx, "memory-process", map[string]any{"project": "fixture", "limit": 2})
		if e != nil || !handled || v["processed"] != 0 {
			t.Fatal(v, handled, e)
		}
	}
	db, e := sql.Open("sqlite", "file:"+path+"?mode=ro")
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	var n int
	if e = db.QueryRowContext(ctx, "SELECT count(*) FROM operation_results").Scan(&n); e != nil || n != 0 {
		t.Fatal("polling appended receipts", n, e)
	}
	if _, handled, e := r.ReadMaintenance(ctx, "candidate-automate", map[string]any{}); e != nil || handled {
		t.Fatal("read path accepted a write capability", handled, e)
	}
}
