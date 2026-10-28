package retrieval

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestSemanticProtocolCachingAndFusion(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		var input struct {
			Model    string   `json:"model"`
			Input    []string `json:"input"`
			Truncate bool     `json:"truncate"`
		}
		if r.Method != "POST" || r.URL.Path != "/api/embed" || json.NewDecoder(r.Body).Decode(&input) != nil || input.Truncate || input.Model != "fixture-model" {
			t.Error("unexpected embedding protocol")
			w.WriteHeader(400)
			return
		}
		vectors := [][]float64{}
		for _, text := range input.Input {
			switch {
			case strings.Contains(text, "排队") || strings.Contains(text, "enqueue"):
				vectors = append(vectors, []float64{1, 0})
			default:
				vectors = append(vectors, []float64{0, 1})
			}
		}
		json.NewEncoder(w).Encode(map[string]any{"model": input.Model, "embeddings": vectors})
	}))
	defer server.Close()
	adapter, err := NewSemantic(Config{Endpoint: server.URL + "/api/embed", Model: "fixture-model", MinSimilarity: .7, MaxDocuments: 10, TimeoutMS: 1000})
	if err != nil {
		t.Fatal(err)
	}
	defer adapter.Close()
	docs := []Document{{"queue", "enqueue the following instruction"}, {"restart", "restart the server"}}
	for i := 0; i < 2; i++ {
		result, e := adapter.Rank(context.Background(), "任务排队", docs, 5)
		if e != nil || !reflect.DeepEqual(result.IDs, []string{"queue"}) || result.CacheHits != i*2 {
			t.Fatal(result, e)
		}
	}
	if calls.Load() != 3 {
		t.Fatal("document cache ineffective", calls.Load())
	}
	if got := Fuse([]string{"restart", "queue", "queue"}, []string{"queue", "novel"}); !reflect.DeepEqual(got, []string{"queue", "restart", "novel"}) {
		t.Fatal("RRF rank/duplicate handling", got)
	}
}

func TestSemanticRejectsMalformedVectorsAndStopsOnTimeout(t *testing.T) {
	for _, body := range []string{
		`{"model":"m","embeddings":[[0,0]]}`, `{"model":"other","embeddings":[[1,0]]}`,
		`{"model":"m","embeddings":[]}`, `{"model":"m","embeddings":[[1,2],[1]]}`,
		`{"model":"m","embeddings":[[1e999,0]]}`, `{"model":"m","embeddings":[[1,0]]}garbage`,
	} {
		t.Run(body, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(body)) }))
			defer server.Close()
			s, e := NewSemantic(Config{server.URL + "/api/embed", "m", .7, 10, 1000})
			if e != nil {
				t.Fatal(e)
			}
			defer s.Close()
			if _, err := s.Rank(context.Background(), "query", nil, 1); err == nil {
				t.Fatal("invalid provider response accepted")
			}
		})
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
		case <-time.After(300 * time.Millisecond):
		}
	}))
	defer server.Close()
	s, _ := NewSemantic(Config{server.URL + "/api/embed", "m", .7, 10, 100})
	defer s.Close()
	before := time.Now()
	if _, err := s.Rank(context.Background(), "query", nil, 1); err == nil || time.Since(before) > time.Second {
		t.Fatal("timeout not bounded", err)
	}
	for _, endpoint := range []string{"http://example.com:11434/api/embed", "http://127.0.0.1:11434/api/embed?key=abc", "http://u:p@127.0.0.1:11434/api/embed", "http://127.0.0.1:11434/other"} {
		if _, err := NewSemantic(Config{endpoint, "m", .7, 10, 1000}); err == nil {
			t.Fatal("unsafe config accepted", endpoint)
		}
	}
}
