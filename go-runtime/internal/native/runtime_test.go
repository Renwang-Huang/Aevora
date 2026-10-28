package native

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestNativeOperationIsAtomicBoundAndIdempotent(t *testing.T) {
	root, e := os.MkdirTemp("", "av-engine-")
	if e != nil {
		t.Fatal(e)
	}
	defer os.RemoveAll(root)
	ctx := context.Background()
	store, e := storage.Open(ctx, filepath.Join(root, "experience.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	scope := engine.RunContext{BackendID: "owned-backend", WorkspaceID: "workspace", RunID: "native-test", Facts: json.RawMessage(`{"worker_count":1.0}`), FactsVersion: "public-context/1", FactsSource: "protected_host_profile"}
	r, e := New(ctx, store, scope)
	if e != nil {
		store.Close()
		t.Fatal(e)
	}
	defer r.Close()
	dispatched := 0
	call := func(id, args string) (json.RawMessage, error) {
		return r.Call(ctx, scope, engine.Request{ID: id, Operation: "resolve_experience", Arguments: json.RawMessage(args), BeforeDispatch: func() error { dispatched++; return nil }})
	}
	id := strings.Repeat("a", 64)
	first, e := call(id, `{"task_context":{}}`)
	if e != nil {
		t.Fatal(e)
	}
	second, e := call(id, `{"task_context":{}}`)
	if e != nil || string(first) != string(second) {
		t.Fatal("same operation replay changed result", e)
	}
	n, e := store.Read().Count(ctx, "Query", scope.RunID)
	if e != nil || n != 1 {
		t.Fatal("operation executed twice", n, e)
	}
	if _, e = call(strings.Repeat("b", 64), `{"task_context":{"worker_count":1}}`); !errors.Is(e, engine.ErrInvalid) {
		t.Fatal("float fact lost", e)
	}
	if _, e = call(id, `{"task_context":{"worker_count":1.0}}`); !errors.Is(e, engine.ErrRecord) {
		t.Fatal("same key different request accepted", e)
	}
	n, e = store.Read().Count(ctx, "Query", scope.RunID)
	if e != nil || n != 1 {
		t.Fatal("failed operation changed graph", n, e)
	}
	if dispatched != 4 {
		t.Fatal(dispatched)
	}
	// A delivery-bound failure occurs before commit, leaving neither business
	// records nor a cached operation result. A retry can execute after rollback.
	limitedID := strings.Repeat("c", 64)
	request := engine.Request{ID: limitedID, Operation: "resolve_experience", Arguments: json.RawMessage(`{"task_context":{}}`), BeforeDispatch: func() error { return nil }, ValidateResult: func(json.RawMessage) error { return engine.ErrResultLimit }}
	if _, e = r.Call(ctx, scope, request); !errors.Is(e, engine.ErrResultLimit) {
		t.Fatal("delivery bound not preserved", e)
	}
	n, e = store.Read().Count(ctx, "Query", scope.RunID)
	if e != nil || n != 1 {
		t.Fatal("rejected delivery committed Query", n, e)
	}
	info, e := store.Read().OperationInfo(ctx, limitedID)
	if e != nil || info["status"] != "NOT_FOUND" {
		t.Fatal("rejected delivery cached success", info, e)
	}
	request.ValidateResult = nil
	if _, e = r.Call(ctx, scope, request); e != nil {
		t.Fatal("rollback prevented retry", e)
	}
	n, e = store.Read().Count(ctx, "Query", scope.RunID)
	if e != nil || n != 2 {
		t.Fatal("retry did not commit exactly once", n, e)
	}
	changed := scope
	changed.Facts = json.RawMessage(`{"worker_count":2.0}`)
	if _, e = New(ctx, store, changed); !errors.Is(e, engine.ErrRunContext) {
		t.Fatal("persisted Run facts drift", e)
	}
}
