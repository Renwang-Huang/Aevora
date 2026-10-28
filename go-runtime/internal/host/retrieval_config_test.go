package host

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestOptionalRetrievalProfileIsStrictAndBackwardCompatible(t *testing.T) {
	root := t.TempDir()
	os.Chmod(root, 0700)
	p := Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind = "sqlite"
	p.Database.Path = filepath.Join(root, "graph.db")
	p.Session.Root = filepath.Join(root, "sessions")
	p.Session.Facts = json.RawMessage(`{}`)
	p.Console.Port = 17805
	path := filepath.Join(root, "host.json")
	save := func(v any) {
		t.Helper()
		raw, _ := json.Marshal(v)
		if e := os.WriteFile(path, raw, 0600); e != nil {
			t.Fatal(e)
		}
	}
	save(p)
	if _, e := Load(path); e != nil {
		t.Fatal("legacy v2 profile rejected", e)
	}
	p.Retrieval = &retrieval.Config{Endpoint: "http://127.0.0.1:11434/api/embed", Model: "fixture", MinSimilarity: .7, MaxDocuments: 2000, TimeoutMS: 1000}
	save(p)
	loaded, e := Load(path)
	if e != nil || loaded.Retrieval == nil {
		t.Fatal("optional provider rejected", e)
	}
	raw, _ := json.Marshal(p)
	var v map[string]any
	json.Unmarshal(raw, &v)
	v["retrieval"].(map[string]any)["unknown"] = true
	save(v)
	if _, e := Load(path); e == nil {
		t.Fatal("unrecognized retrieval config accepted")
	}
	p.Retrieval.Endpoint = "http://example.com:11434/api/embed"
	save(p)
	if _, e := Load(path); e == nil {
		t.Fatal("non-loopback provider accepted")
	}
}

func TestOptionalRerankerProfileRequiresPinnedExplicitPolicy(t *testing.T) {
	root := t.TempDir()
	os.Chmod(root, 0700)
	p := Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind = "sqlite"
	p.Database.Path = filepath.Join(root, "graph.db")
	p.Session.Root = filepath.Join(root, "sessions")
	p.Session.Facts = json.RawMessage(`{}`)
	p.Console.Port = 17805
	threshold := 0.0
	p.Reranker = &retrieval.RerankConfig{Endpoint: "http://127.0.0.1:8080/rerank", Model: "public/fixture", Revision: strings.Repeat("a", 40), MinScore: &threshold, MaxCandidates: 32, TimeoutMS: 1000, OnFailure: "ABSTAIN"}
	path := filepath.Join(root, "host.json")
	save := func() {
		raw, _ := json.Marshal(p)
		if e := os.WriteFile(path, raw, 0600); e != nil {
			t.Fatal(e)
		}
	}
	save()
	if loaded, e := Load(path); e != nil || loaded.Reranker == nil {
		t.Fatal(loaded, e)
	}
	p.Reranker.MinScore = nil
	save()
	if _, e := Load(path); e == nil {
		t.Fatal("implicit threshold accepted")
	}
	p.Reranker.MinScore = &threshold
	p.Reranker.Revision = "main"
	save()
	if _, e := Load(path); e == nil {
		t.Fatal("mutable revision accepted")
	}
	p.Reranker.Revision = strings.Repeat("a", 40)
	p.Reranker.OnFailure = ""
	save()
	if _, e := Load(path); e == nil {
		t.Fatal("implicit failure policy accepted")
	}
}
