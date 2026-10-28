package retrieval

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"math"
	"net"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Config is protected Host configuration, never accepted as MCP arguments.
// The optional adapter uses Ollama's official /api/embed protocol on loopback.
type Config struct {
	Endpoint      string  `json:"endpoint"`
	Model         string  `json:"model"`
	MinSimilarity float64 `json:"min_similarity"`
	MaxDocuments  int     `json:"max_documents"`
	TimeoutMS     int     `json:"timeout_ms"`
}

var ErrEmbedding = errors.New("SEMANTIC_PROVIDER_UNAVAILABLE_OR_INVALID")

func (c Config) Validate() error {
	u, err := url.Parse(c.Endpoint)
	if err != nil || u.Scheme != "http" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Path != "/api/embed" {
		return ErrEmbedding
	}
	ip := net.ParseIP(u.Hostname())
	port, err := strconv.Atoi(u.Port())
	if ip == nil || !ip.IsLoopback() || err != nil || port < 1 || port > 65535 || strings.TrimSpace(c.Model) != c.Model || c.Model == "" || len(c.Model) > 128 || strings.ContainsAny(c.Model, "\r\n\x00") {
		return ErrEmbedding
	}
	if math.IsNaN(c.MinSimilarity) || math.IsInf(c.MinSimilarity, 0) || c.MinSimilarity < 0.1 || c.MinSimilarity > 1 || c.MaxDocuments < 1 || c.MaxDocuments > 4096 || c.TimeoutMS < 100 || c.TimeoutMS > 30000 {
		return ErrEmbedding
	}
	return nil
}

type Document struct{ ID, Text string }
type SemanticResult struct {
	IDs                  []string
	Documents, CacheHits int
	InputClipped         bool
}
type cachedVector struct {
	vector []float64
	at     time.Time
}
type Semantic struct {
	config     Config
	client     *http.Client
	mu         sync.Mutex
	cache      map[string]cachedVector
	cacheBytes int
}

func NewSemantic(c Config) (*Semantic, error) {
	if err := c.Validate(); err != nil {
		return nil, err
	}
	// No environment proxy, redirects, cookies or credentials. Only public
	// narrative text is sent to an explicitly configured loopback endpoint.
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	return &Semantic{config: c, client: &http.Client{Transport: transport, CheckRedirect: func(*http.Request, []*http.Request) error { return ErrEmbedding }}, cache: map[string]cachedVector{}}, nil
}
func (s *Semantic) Config() Config { return s.config }
func (s *Semantic) Close()         { s.client.CloseIdleConnections() }

func vector(v []float64) ([]float64, error) {
	if len(v) < 1 || len(v) > 2048 {
		return nil, ErrEmbedding
	}
	// Normalize with scaling to avoid overflow from malformed finite values.
	scale := 0.0
	for _, x := range v {
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return nil, ErrEmbedding
		}
		scale = math.Max(scale, math.Abs(x))
	}
	if scale == 0 {
		return nil, ErrEmbedding
	}
	sum := 0.0
	for _, x := range v {
		sum += (x / scale) * (x / scale)
	}
	norm := math.Sqrt(sum)
	out := make([]float64, len(v))
	for i, x := range v {
		out[i] = (x / scale) / norm
	}
	return out, nil
}

func (s *Semantic) embed(ctx context.Context, texts []string) ([][]float64, error) {
	raw, err := json.Marshal(map[string]any{"model": s.config.Model, "input": texts, "truncate": false})
	if err != nil {
		return nil, ErrEmbedding
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.config.Endpoint, bytes.NewReader(raw))
	if err != nil {
		return nil, ErrEmbedding
	}
	req.Header.Set("Content-Type", "application/json")
	res, err := s.client.Do(req)
	if err != nil {
		return nil, ErrEmbedding
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		return nil, ErrEmbedding
	}
	data, err := io.ReadAll(io.LimitReader(res.Body, 4*1024*1024+1))
	if err != nil || len(data) > 4*1024*1024 {
		return nil, ErrEmbedding
	}
	var body struct {
		Model      string      `json:"model"`
		Embeddings [][]float64 `json:"embeddings"`
	}
	if json.Unmarshal(data, &body) != nil || body.Model != s.config.Model || len(body.Embeddings) != len(texts) {
		return nil, ErrEmbedding
	}
	dimension := 0
	for i, v := range body.Embeddings {
		n, e := vector(v)
		if e != nil {
			return nil, e
		}
		if dimension != 0 && dimension != len(n) {
			return nil, ErrEmbedding
		}
		dimension = len(n)
		body.Embeddings[i] = n
	}
	return body.Embeddings, nil
}
func cacheKey(text string) string { h := sha256.Sum256([]byte(text)); return hex.EncodeToString(h[:]) }

func (s *Semantic) Rank(ctx context.Context, query string, docs []Document, take int) (SemanticResult, error) {
	result := SemanticResult{IDs: []string{}, Documents: len(docs)}
	if take < 1 || take > 100 || len(docs) > s.config.MaxDocuments {
		return result, ErrEmbedding
	}
	ctx, cancel := context.WithTimeout(ctx, time.Duration(s.config.TimeoutMS)*time.Millisecond)
	defer cancel()
	q, err := s.embed(ctx, []string{query})
	if err != nil {
		return result, err
	}
	vectors := make([][]float64, len(docs))
	missing := []int{}
	texts := make([]string, len(docs))
	for i, doc := range docs {
		text := []rune(doc.Text)
		if len(text) > 2000 {
			text = text[:2000]
			result.InputClipped = true
		}
		texts[i] = string(text)
		key := cacheKey(texts[i])
		s.mu.Lock()
		v, ok := s.cache[key]
		s.mu.Unlock()
		if ok && time.Since(v.at) < 5*time.Minute && len(v.vector) == len(q[0]) {
			vectors[i] = v.vector
			result.CacheHits++
		} else {
			missing = append(missing, i)
		}
	}
	for start := 0; start < len(missing); start += 16 {
		end := start + 16
		if end > len(missing) {
			end = len(missing)
		}
		batch := []string{}
		for _, i := range missing[start:end] {
			batch = append(batch, texts[i])
		}
		vs, e := s.embed(ctx, batch)
		if e != nil {
			return result, e
		}
		for j, i := range missing[start:end] {
			if len(vs[j]) != len(q[0]) {
				return result, ErrEmbedding
			}
			vectors[i] = vs[j]
			key := cacheKey(texts[i])
			s.mu.Lock()
			if s.cacheBytes+len(vs[j])*8 > 32*1024*1024 {
				s.cache = map[string]cachedVector{}
				s.cacheBytes = 0
			}
			if old, ok := s.cache[key]; ok {
				s.cacheBytes -= len(old.vector) * 8
			}
			s.cache[key] = cachedVector{vs[j], time.Now()}
			s.cacheBytes += len(vs[j]) * 8
			s.mu.Unlock()
		}
	}
	type scored struct {
		id    string
		score float64
	}
	scores := []scored{}
	for i, doc := range docs {
		score := 0.0
		for j, x := range vectors[i] {
			score += x * q[0][j]
		}
		if score >= s.config.MinSimilarity {
			scores = append(scores, scored{doc.ID, score})
		}
	}
	sort.Slice(scores, func(i, j int) bool {
		if scores[i].score == scores[j].score {
			return scores[i].id < scores[j].id
		}
		return scores[i].score > scores[j].score
	})
	for _, v := range scores {
		if len(result.IDs) == take {
			break
		}
		result.IDs = append(result.IDs, v.id)
	}
	return result, nil
}

// Fuse implements reciprocal rank fusion (k=60). It is relevance rank, not
// confidence, verified applicability, adoption or task success probability.
func Fuse(lists ...[]string) []string {
	scores := map[string]float64{}
	for _, list := range lists {
		seen := map[string]bool{}
		for i, id := range list {
			if !seen[id] {
				scores[id] += 1 / float64(61+i)
				seen[id] = true
			}
		}
	}
	out := []string{}
	for id := range scores {
		out = append(out, id)
	}
	sort.Slice(out, func(i, j int) bool {
		if scores[out[i]] == scores[out[j]] {
			return out[i] < out[j]
		}
		return scores[out[i]] > scores[out[j]]
	})
	return out
}
