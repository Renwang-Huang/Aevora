package cli_test

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/cli"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestOfflineCLIUsesSameProtectedRetrievalConfiguration(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	os.Chmod(root, 0700)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var in struct {
			Model string   `json:"model"`
			Input []string `json:"input"`
		}
		if json.NewDecoder(r.Body).Decode(&in) != nil {
			w.WriteHeader(400)
			return
		}
		vectors := [][]float64{}
		for range in.Input {
			vectors = append(vectors, []float64{1, 0})
		}
		json.NewEncoder(w).Encode(map[string]any{"model": in.Model, "embeddings": vectors})
	}))
	defer server.Close()
	database := filepath.Join(root, "graph.db")
	store, e := storage.Open(ctx, database, storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	e = store.Write(ctx, func(r *storage.Repository) error {
		return r.PutNode(ctx, "Experience", domain.Map{"id": "experience:offline", "title": "enqueue subsequent instructions", "strategy": "enqueue after completion", "public_summary": "Synthetic integration fixture; no utility proof", "source_type": "synthetic_or_test_fixture"})
	})
	store.Close()
	if e != nil {
		t.Fatal(e)
	}
	p := host.Profile{Schema: "aevora.host-config/2", Retrieval: &retrieval.Config{Endpoint: server.URL + "/api/embed", Model: "fixture", MinSimilarity: .7, MaxDocuments: 10, TimeoutMS: 1000}}
	p.Database.Kind = "sqlite"
	p.Database.Path = database
	p.Session.Root = filepath.Join(root, "sessions")
	p.Session.Facts = json.RawMessage(`{}`)
	p.Console.Port = 17805
	os.Mkdir(p.Session.Root, 0700)
	profile := filepath.Join(root, "host.json")
	raw, _ := json.Marshal(p)
	os.WriteFile(profile, raw, 0600)
	registry := host.RegistryDir(host.BackendID(p))
	defer func() { os.Remove(filepath.Join(registry, "binding.json")); os.Remove(registry) }()
	var out, stderr bytes.Buffer
	code := cli.Execute(ctx, []string{"--config", profile, "query", "--query", "排队"}, bytes.NewReader(nil), &out, &stderr, native.Factory())
	if code != 0 {
		t.Fatal("offline query failed", code, stderr.String())
	}
	value, e := codec.Parse(out.Bytes())
	if e != nil {
		t.Fatal(e)
	}
	result := domain.M(domain.M(value)["result"])
	if domain.M(result["retrieval"])["semantic_recall"] != "READY" || len(domain.A(result["candidates"])) != 1 {
		t.Fatal("offline configuration silently ignored", result)
	}
}
