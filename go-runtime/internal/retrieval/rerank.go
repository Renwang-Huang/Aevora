package retrieval

import (
	"bytes"
	"context"
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
	"time"
)

var ErrRerank = errors.New("RERANKER_UNAVAILABLE_OR_INVALID")

// RerankConfig is protected Host configuration. TEI returns raw model logits,
// so a minimum must be chosen explicitly for the pinned model/evaluation.
type RerankConfig struct {
	Endpoint      string   `json:"endpoint"`
	Model         string   `json:"model"`
	Revision      string   `json:"revision"`
	MinScore      *float64 `json:"min_score"`
	MaxCandidates int      `json:"max_candidates"`
	TimeoutMS     int      `json:"timeout_ms"`
	OnFailure     string   `json:"on_failure"`
}

func (c RerankConfig) Validate() error {
	u, e := url.Parse(c.Endpoint)
	if e != nil || u.Scheme != "http" || u.User != nil || u.Path != "/rerank" || u.RawQuery != "" || u.Fragment != "" {
		return ErrRerank
	}
	ip := net.ParseIP(u.Hostname())
	port, e := strconv.Atoi(u.Port())
	if ip == nil || !ip.IsLoopback() || e != nil || port < 1 || port > 65535 || c.Model == "" || strings.TrimSpace(c.Model) != c.Model || len(c.Model) > 128 || strings.HasPrefix(c.Model, "/") || strings.ContainsAny(c.Model, "\r\n\x00") {
		return ErrRerank
	}
	rev, e := hex.DecodeString(c.Revision)
	if e != nil || (len(rev) != 20 && len(rev) != 32) || c.Revision != strings.ToLower(c.Revision) {
		return ErrRerank
	}
	if c.MinScore == nil || math.IsNaN(*c.MinScore) || math.IsInf(*c.MinScore, 0) || math.Abs(*c.MinScore) > 1e6 || c.MaxCandidates < 1 || c.MaxCandidates > 64 || c.TimeoutMS < 100 || c.TimeoutMS > 30000 || (c.OnFailure != "ABSTAIN" && c.OnFailure != "PRE_RERANK_FALLBACK") {
		return ErrRerank
	}
	return nil
}

type Reranker struct {
	config RerankConfig
	client *http.Client
	slots  chan struct{}
}
type RerankResult struct {
	IDs              []string
	Scored, Rejected int
	InputClipped     bool
}

func NewReranker(c RerankConfig) (*Reranker, error) {
	if e := c.Validate(); e != nil {
		return nil, e
	}
	threshold := *c.MinScore
	c.MinScore = &threshold
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	return &Reranker{c, &http.Client{Transport: transport, CheckRedirect: func(*http.Request, []*http.Request) error { return ErrRerank }}, make(chan struct{}, 1)}, nil
}
func (r *Reranker) Config() RerankConfig {
	c := r.config
	threshold := *c.MinScore
	c.MinScore = &threshold
	return c
}
func (r *Reranker) Close() { r.client.CloseIdleConnections() }
func (r *Reranker) request(ctx context.Context, method, endpoint string, raw []byte, limit int) ([]byte, error) {
	req, e := http.NewRequestWithContext(ctx, method, endpoint, bytes.NewReader(raw))
	if e != nil {
		return nil, ErrRerank
	}
	if method == http.MethodPost {
		req.Header.Set("Content-Type", "application/json")
	}
	response, e := r.client.Do(req)
	if e != nil {
		return nil, ErrRerank
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, ErrRerank
	}
	body, e := io.ReadAll(io.LimitReader(response.Body, int64(limit+1)))
	if e != nil || len(body) > limit {
		return nil, ErrRerank
	}
	return body, nil
}
func (r *Reranker) identity(ctx context.Context) error {
	endpoint := strings.TrimSuffix(r.config.Endpoint, "/rerank") + "/info"
	raw, e := r.request(ctx, http.MethodGet, endpoint, nil, 65536)
	if e != nil {
		return e
	}
	var info struct {
		Model    string                     `json:"model_id"`
		Revision string                     `json:"model_sha"`
		Type     map[string]json.RawMessage `json:"model_type"`
	}
	if json.Unmarshal(raw, &info) != nil || info.Model != r.config.Model || info.Revision != r.config.Revision || len(info.Type) != 1 || len(info.Type["reranker"]) == 0 || string(info.Type["reranker"]) == "null" {
		return ErrRerank
	}
	return nil
}
func (r *Reranker) Rank(ctx context.Context, query string, docs []Document) (RerankResult, error) {
	result := RerankResult{IDs: []string{}}
	if len(docs) > r.config.MaxCandidates || len(query) > 4000 {
		return result, ErrRerank
	}
	if len(docs) == 0 {
		return result, nil
	}
	ctx, cancel := context.WithTimeout(ctx, time.Duration(r.config.TimeoutMS)*time.Millisecond)
	defer cancel()
	select {
	case r.slots <- struct{}{}:
		defer func() { <-r.slots }()
	case <-ctx.Done():
		return result, ErrRerank
	}
	if e := r.identity(ctx); e != nil {
		return result, e
	}
	texts := []string{}
	seen := map[string]bool{}
	for _, d := range docs {
		if d.ID == "" || seen[d.ID] {
			return result, ErrRerank
		}
		seen[d.ID] = true
		text := []rune(d.Text)
		if len(text) > 2000 {
			text = text[:2000]
			result.InputClipped = true
		}
		texts = append(texts, string(text))
	}
	body, e := json.Marshal(map[string]any{"query": query, "texts": texts, "raw_scores": true, "return_text": false, "truncate": false})
	if e != nil || len(body) > 1024*1024 {
		return result, ErrRerank
	}
	raw, e := r.request(ctx, http.MethodPost, r.config.Endpoint, body, 65536)
	if e != nil {
		return result, e
	}
	var scores []struct {
		Index *int     `json:"index"`
		Score *float64 `json:"score"`
	}
	if json.Unmarshal(raw, &scores) != nil || len(scores) != len(docs) {
		return result, ErrRerank
	}
	type ranked struct {
		ID    string
		Score float64
	}
	accepted := []ranked{}
	indices := map[int]bool{}
	for _, s := range scores {
		if s.Index == nil || s.Score == nil || *s.Index < 0 || *s.Index >= len(docs) || indices[*s.Index] || math.IsNaN(*s.Score) || math.IsInf(*s.Score, 0) {
			return result, ErrRerank
		}
		indices[*s.Index] = true
		if *s.Score >= *r.config.MinScore {
			accepted = append(accepted, ranked{docs[*s.Index].ID, *s.Score})
		} else {
			result.Rejected++
		}
	}
	if e = r.identity(ctx); e != nil {
		return result, e
	}
	sort.Slice(accepted, func(i, j int) bool {
		if accepted[i].Score == accepted[j].Score {
			return accepted[i].ID < accepted[j].ID
		}
		return accepted[i].Score > accepted[j].Score
	})
	for _, v := range accepted {
		result.IDs = append(result.IDs, v.ID)
	}
	result.Scored = len(scores)
	return result, nil
}
