package native

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
)

func TestRerankNativeFilteringFallbackReplayAndWriterIsolation(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	root := t.TempDir()
	os.Chmod(root, 0700)
	store, e := storage.Open(ctx, filepath.Join(root, "graph.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	scope := engine.RunContext{BackendID: "rerank-fixture", WorkspaceID: "fixture", RunID: "rerank-run", Facts: json.RawMessage(`{}`), FactsVersion: "public-context/1", FactsSource: "protected_host_profile"}
	r, e := New(ctx, store, scope)
	if e != nil {
		t.Fatal(e)
	}
	defer r.Close()
	if e = store.Write(ctx, func(repo *storage.Repository) error {
		for i := 0; i < 2; i++ {
			if e := repo.PutNode(ctx, "Experience", domain.Map{"id": fmt.Sprintf("experience:rerank:%d", i), "title": "restart server", "public_summary": "Public synthetic fixture", "strategy": "Review server restart", "source_type": "synthetic_or_test_fixture", "private_evidence": "NEVER_SEND_PRIVATE"}); e != nil {
				return e
			}
		}
		return nil
	}); e != nil {
		t.Fatal(e)
	}
	var mode, calls atomic.Int32
	entered := make(chan struct{}, 1)
	release := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		calls.Add(1)
		if mode.Load() == 2 {
			w.WriteHeader(503)
			return
		}
		if req.URL.Path == "/info" {
			json.NewEncoder(w).Encode(map[string]any{"model_id": "public/fixture", "model_sha": strings.Repeat("a", 40), "model_type": map[string]any{"reranker": map[string]any{}}})
			return
		}
		var body struct {
			Texts []string `json:"texts"`
		}
		json.NewDecoder(req.Body).Decode(&body)
		for _, text := range body.Texts {
			if strings.Contains(text, "NEVER_SEND_PRIVATE") {
				t.Error("private payload sent")
			}
		}
		if mode.Load() == 3 {
			entered <- struct{}{}
			select {
			case <-release:
			case <-req.Context().Done():
				return
			}
		}
		scores := []map[string]any{}
		for i := range body.Texts {
			score := -3.0
			if i == 1 && mode.Load() != 1 {
				score = 2
			}
			scores = append(scores, map[string]any{"index": i, "score": score})
		}
		json.NewEncoder(w).Encode(scores)
	}))
	defer server.Close()
	threshold := 0.0
	config := retrieval.RerankConfig{Endpoint: server.URL + "/rerank", Model: "public/fixture", Revision: strings.Repeat("a", 40), MinScore: &threshold, MaxCandidates: 8, TimeoutMS: 1000, OnFailure: "ABSTAIN"}
	r.reranker, e = retrieval.NewReranker(config)
	if e != nil {
		t.Fatal(e)
	}
	n := 0
	request := func(query string) engine.Request {
		n++
		raw, _ := json.Marshal(domain.Map{"task_context": domain.Map{}, "query": query})
		return engine.Request{ID: fmt.Sprintf("rerank-%d", n), Operation: "resolve_experience", Arguments: raw, BeforeDispatch: func() error { return nil }}
	}
	call := func(req engine.Request) domain.Map {
		t.Helper()
		raw, e := r.Call(ctx, scope, req)
		if e != nil {
			t.Fatal(e)
		}
		v, e := codec.Parse(raw)
		if e != nil {
			t.Fatal(e)
		}
		return domain.M(v)
	}
	req := request("restart")
	first := call(req)
	cards := domain.A(first["candidates"])
	if len(cards) != 1 || domain.M(cards[0])["experience_id"] != "experience:rerank:1" || domain.M(cards[0])["decision"] == "APPLY" || domain.M(first["retrieval"])["reranker"] != "READY" {
		t.Fatal(first)
	}
	before := calls.Load()
	again := call(req)
	if domain.H(first) != domain.H(again) || calls.Load() != before {
		t.Fatal("replay re-entered reranker")
	}
	mode.Store(1)
	if v := call(request("restart")); len(domain.A(v["candidates"])) != 0 || domain.M(v["retrieval"])["reranker"] != "READY" {
		t.Fatal("low scores silently fell back", v)
	}
	mode.Store(2)
	if v := call(request("restart")); len(domain.A(v["candidates"])) != 0 || domain.M(v["retrieval"])["reranker"] != "UNAVAILABLE" {
		t.Fatal("failure policy not applied", v)
	}
	r.reranker.Close()
	config.OnFailure = "PRE_RERANK_FALLBACK"
	r.reranker, _ = retrieval.NewReranker(config)
	if v := call(request("restart")); len(domain.A(v["candidates"])) != 2 || domain.M(v["retrieval"])["reranker"] != "UNAVAILABLE" {
		t.Fatal("explicit fallback unavailable", v)
	}
	mode.Store(3)
	done := make(chan error, 1)
	blocked := request("restart")
	go func() { _, e := r.Call(ctx, scope, blocked); done <- e }()
	select {
	case <-entered:
	case <-time.After(time.Second):
		t.Fatal("reranker not entered")
	}
	writeCtx, stop := context.WithTimeout(ctx, 300*time.Millisecond)
	e = store.Write(writeCtx, func(repo *storage.Repository) error {
		return repo.PutNode(writeCtx, "Experience", domain.Map{"id": "experience:concurrent", "title": "new unrelated fixture"})
	})
	stop()
	close(release)
	if e != nil {
		t.Fatal("provider held SQLite writer", e)
	}
	if e = <-done; e != nil {
		t.Fatal(e)
	}
	before = calls.Load()
	v := call(request("absent encryption rotation"))
	if domain.M(v["retrieval"])["reranker"] != "NOT_RUN_NO_CANDIDATES" || calls.Load() != before {
		t.Fatal("empty lane falsely reported model ready", v)
	}
}
