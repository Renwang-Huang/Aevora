package retrieval

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func rerankConfig(endpoint string) RerankConfig {
	threshold := 0.0
	return RerankConfig{Endpoint: endpoint, Model: "public/fixture", Revision: strings.Repeat("a", 40), MinScore: &threshold, MaxCandidates: 8, TimeoutMS: 1000, OnFailure: "ABSTAIN"}
}
func fixtureInfo(w http.ResponseWriter, revision string) {
	json.NewEncoder(w).Encode(map[string]any{"model_id": "public/fixture", "model_sha": revision, "model_type": map[string]any{"reranker": map[string]any{"id2label": map[string]string{"0": "LABEL"}}}})
}

func TestRerankerPinsIdentityRawScoresAndRejectsIncompleteResults(t *testing.T) {
	var mode atomic.Int32
	var infos atomic.Int32
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/info" {
			n := infos.Add(1)
			rev := strings.Repeat("a", 40)
			if mode.Load() == 3 && n%2 == 0 {
				rev = strings.Repeat("b", 40)
			}
			fixtureInfo(w, rev)
			return
		}
		var request struct {
			Query    string   `json:"query"`
			Texts    []string `json:"texts"`
			Raw      bool     `json:"raw_scores"`
			Return   bool     `json:"return_text"`
			Truncate bool     `json:"truncate"`
		}
		if json.NewDecoder(r.Body).Decode(&request) != nil || !request.Raw || request.Return || request.Truncate || len(request.Texts) != 2 {
			t.Error("wrong official request", request)
		}
		switch mode.Load() {
		case 1:
			w.Write([]byte(`[{"index":0,"score":1},{"index":0,"score":2}]`))
		case 2:
			w.Write([]byte(`[{"index":0,"score":1}]`))
		case 4:
			w.Write([]byte(`[{"index":0},{"index":1,"score":1}]`))
		default:
			w.Write([]byte(`[{"index":1,"score":3},{"index":0,"score":-2}]`))
		}
	}))
	defer s.Close()
	r, e := NewReranker(rerankConfig(s.URL + "/rerank"))
	if e != nil {
		t.Fatal(e)
	}
	defer r.Close()
	docs := []Document{{"a", "Public alpha"}, {"b", "Public beta"}}
	v, e := r.Rank(context.Background(), "task", docs)
	if e != nil || len(v.IDs) != 1 || v.IDs[0] != "b" || v.Rejected != 1 {
		t.Fatal(v, e)
	}
	for _, n := range []int32{1, 2, 3, 4} {
		mode.Store(n)
		infos.Store(0)
		if _, e = r.Rank(context.Background(), "task", docs); e == nil {
			t.Fatal("invalid or changed model accepted", n)
		}
	}
}

func TestRerankerRejectsNetworkEscapeAndHonorsTimeout(t *testing.T) {
	for _, endpoint := range []string{"http://example.com:80/rerank", "http://127.0.0.1:1/embed", "http://user:pass@127.0.0.1:1/rerank", "http://127.0.0.1:1/rerank?token=secret"} {
		if _, e := NewReranker(rerankConfig(endpoint)); e == nil {
			t.Fatal("unsafe endpoint", endpoint)
		}
	}
	var external atomic.Int32
	outside := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { external.Add(1) }))
	defer outside.Close()
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, outside.URL, http.StatusFound) }))
	defer s.Close()
	r, _ := NewReranker(rerankConfig(s.URL + "/rerank"))
	defer r.Close()
	if _, e := r.Rank(context.Background(), "task", []Document{{"a", "public"}}); e == nil || external.Load() != 0 {
		t.Fatal("redirect followed", e)
	}
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
		case <-time.After(time.Second):
		}
	}))
	defer slow.Close()
	c := rerankConfig(slow.URL + "/rerank")
	c.TimeoutMS = 100
	r2, _ := NewReranker(c)
	defer r2.Close()
	start := time.Now()
	if _, e := r2.Rank(context.Background(), "task", []Document{{"a", "public"}}); e == nil || time.Since(start) > 500*time.Millisecond {
		t.Fatal("deadline failed", e)
	}
}
