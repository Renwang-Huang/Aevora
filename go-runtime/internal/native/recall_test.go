package native

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestHybridRecallNativeManagementFallbackReplayAndWriterIsolation(t *testing.T) {
	ctx := context.Background()
	dir := t.TempDir()
	os.Chmod(dir, 0700)
	store, err := storage.Open(ctx, filepath.Join(dir, "experience.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	scope := engine.RunContext{BackendID: "hybrid-owned", WorkspaceID: "hybrid-workspace", RunID: "hybrid-run", Facts: json.RawMessage(`{}`), FactsVersion: "public-context/1", FactsSource: "protected_host_profile"}
	runtime, err := New(ctx, store, scope)
	if err != nil {
		store.Close()
		t.Fatal(err)
	}
	defer runtime.Close()
	if err = store.Write(ctx, func(repo *storage.Repository) error {
		for _, v := range []struct{ id, title string }{{"experience:enqueue", "enqueue following instructions"}, {"experience:restart", "restart server"}} {
			if e := repo.PutNode(ctx, "Experience", domain.Map{"id": v.id, "title": v.title, "source_type": "synthetic_or_test_fixture", "public_summary": "Synthetic fixture, no adoption proof", "strategy": v.title, "private_evidence": "never-send-private-field"}); e != nil {
				return e
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	var calls atomic.Int64
	var unavailable atomic.Bool
	entered := make(chan struct{}, 1)
	release := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if unavailable.Load() {
			w.WriteHeader(503)
			return
		}
		var input struct {
			Model string   `json:"model"`
			Input []string `json:"input"`
		}
		if json.NewDecoder(r.Body).Decode(&input) != nil {
			w.WriteHeader(400)
			return
		}
		vectors := [][]float64{}
		for _, text := range input.Input {
			if strings.Contains(text, "never-send-private-field") {
				t.Error("private field sent to embeddings")
			}
			if text == "pause" {
				entered <- struct{}{}
				select {
				case <-release:
				case <-r.Context().Done():
				}
			}
			if strings.Contains(text, "排队") || strings.Contains(text, "enqueue") {
				vectors = append(vectors, []float64{1, 0})
			} else {
				vectors = append(vectors, []float64{0, 1})
			}
		}
		json.NewEncoder(w).Encode(map[string]any{"model": input.Model, "embeddings": vectors})
	}))
	defer server.Close()
	runtime.semantic, err = retrieval.NewSemantic(retrieval.Config{Endpoint: server.URL + "/api/embed", Model: "fixture", MinSimilarity: .7, MaxDocuments: 50, TimeoutMS: 1000})
	if err != nil {
		t.Fatal(err)
	}
	n := 0
	request := func(query string) engine.Request {
		n++
		raw, _ := json.Marshal(domain.Map{"task_context": domain.Map{}, "query": query})
		return engine.Request{ID: fmt.Sprintf("hybrid-%d", n), Operation: "resolve_experience", Arguments: raw, BeforeDispatch: func() error { return nil }}
	}
	req := request("任务排队")
	first, err := runtime.Call(ctx, scope, req)
	if err != nil {
		t.Fatal(err)
	}
	decoded, _ := codec.Parse(first)
	out := domain.M(decoded)
	cards := domain.A(out["candidates"])
	if len(cards) != 1 || domain.M(cards[0])["experience_id"] != "experience:enqueue" || domain.M(cards[0])["decision"] == "APPLY" || domain.M(out["retrieval"])["semantic_recall"] != "READY" {
		t.Fatal(out)
	}
	before := calls.Load()
	replay, err := runtime.Call(ctx, scope, req)
	if err != nil || string(first) != string(replay) || calls.Load() != before {
		t.Fatal("replay re-entered provider", err)
	}
	manage := request("任务排队")
	manage.Operation = "query"
	raw, err := runtime.Manage(ctx, manage)
	if err != nil {
		t.Fatal(err)
	}
	decoded, _ = codec.Parse(raw)
	if len(domain.A(domain.M(decoded)["candidates"])) != 1 {
		t.Fatal("management/MCP recall diverged", string(raw))
	}
	unavailable.Store(true)
	raw, err = runtime.Call(ctx, scope, request("任务排队"))
	if err != nil {
		t.Fatal(err)
	}
	decoded, _ = codec.Parse(raw)
	fallback := domain.M(decoded)
	if len(domain.A(fallback["candidates"])) != 0 || domain.M(fallback["retrieval"])["semantic_recall"] != "UNAVAILABLE" {
		t.Fatal("failure did not produce explicit lexical fallback", fallback)
	}
	unavailable.Store(false)
	blocked := request("pause")
	done := make(chan error, 1)
	go func() { _, e := runtime.Call(ctx, scope, blocked); done <- e }()
	select {
	case <-entered:
	case <-time.After(time.Second):
		t.Fatal("provider not reached")
	}
	writeCtx, cancel := context.WithTimeout(ctx, 300*time.Millisecond)
	err = store.Write(writeCtx, func(repo *storage.Repository) error {
		return repo.PutNode(writeCtx, "Experience", domain.Map{"id": "experience:new", "title": "new record", "source_type": "synthetic_or_test_fixture"})
	})
	cancel()
	close(release)
	if err != nil {
		t.Fatal("provider held shared SQLite writer", err)
	}
	if err = <-done; err != nil {
		t.Fatal(err)
	}
	before = calls.Load()
	invalid := request("task")
	invalid.Arguments = json.RawMessage(`{"task_context":{},"query":"/home/private/file"}`)
	if _, err = runtime.Call(ctx, scope, invalid); err == nil || calls.Load() != before {
		t.Fatal("private query reached provider", err)
	}
}
