package storage

import (
	"context"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"
)

//go:embed testdata/retrieval-quality.json
var qualityCorpus []byte

//go:embed testdata/retrieval-challenge.json
var challengeCorpus []byte

// This freezes labels, not a claim that lexical ranking already has good quality.
// Regressions protect governance separately. Do not tune on the heldout labels.
func TestRetrievalQualityBaseline(t *testing.T) {
	runRetrievalQuality(t, qualityCorpus, "AEVORA_QUALITY_REPORT", 10, 60)
}

func TestRetrievalQualityChallenge(t *testing.T) {
	runRetrievalQuality(t, challengeCorpus, "AEVORA_QUALITY_CHALLENGE_REPORT", 16, 50)
}

func runRetrievalQuality(t *testing.T, corpusRaw []byte, reportEnv string, documentCount, queryCount int) {
	t.Helper()
	var corpus struct {
		Schema, Provenance string
		Documents          []map[string]any `json:"documents"`
		Queries            []struct {
			ID, Split, Query, Kind string
			Relevant               []string `json:"relevant_ids"`
		} `json:"queries"`
	}
	if err := json.Unmarshal(corpusRaw, &corpus); err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	root := t.TempDir()
	os.Chmod(root, 0700)
	s, err := Open(ctx, filepath.Join(root, "graph.db"), Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	if err = s.Write(ctx, func(r *Repository) error {
		for _, d := range corpus.Documents {
			if e := r.PutNode(ctx, "Experience", d); e != nil {
				return e
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	type score struct {
		Queries, Answerable, NoAnswer, FalsePositive int
		Recall, MRR, NDCG                            float64
		ReturnedBytes                                int
		durations                                    []int64
	}
	scores := map[string]*score{}
	cases := []map[string]any{}
	for _, method := range []string{"FTS5_BM25", "LITERAL_FILE_SEARCH"} {
		for _, q := range corpus.Queries {
			key := method + "/" + q.Split
			if scores[key] == nil {
				scores[key] = &score{}
			}
			v := scores[key]
			v.Queries++
			started := time.Now()
			ids := []string{}
			if method == "FTS5_BM25" {
				hits, _, e := s.Read().Recall(ctx, "Experience", q.Query, 5, 0)
				if e != nil {
					t.Fatal(e)
				}
				for _, h := range hits {
					ids = append(ids, h.ID)
				}
			} else {
				// Literal case-insensitive terms, all required, in fixed file-name order.
				terms := strings.Fields(strings.ToLower(q.Query))
				for _, d := range corpus.Documents {
					body := strings.ToLower(d["title"].(string) + " " + d["public_summary"].(string) + " " + d["strategy"].(string))
					match := true
					for _, term := range terms {
						if !strings.Contains(body, term) {
							match = false
							break
						}
					}
					if match && len(ids) < 5 {
						ids = append(ids, d["id"].(string))
					}
				}
			}
			v.durations = append(v.durations, time.Since(started).Microseconds())
			raw, _ := json.Marshal(ids)
			v.ReturnedBytes += len(raw)
			if len(q.Relevant) == 0 {
				v.NoAnswer++
				if len(ids) > 0 {
					v.FalsePositive++
				}
			} else {
				v.Answerable++
				recall, mrr, ndcg := qualityRanking(ids, q.Relevant, 5)
				v.Recall += recall
				v.MRR += mrr
				v.NDCG += ndcg
			}
			cases = append(cases, map[string]any{"id": q.ID, "method": method, "split": q.Split, "returned": ids})
		}
	}
	if len(corpus.Queries) != queryCount || len(corpus.Documents) != documentCount {
		t.Fatal("quality corpus changed; version and freeze labels explicitly")
	}
	metrics := map[string]any{}
	for key, v := range scores {
		sort.Slice(v.durations, func(i, j int) bool { return v.durations[i] < v.durations[j] })
		metrics[key] = map[string]any{"queries": v.Queries, "answerable": v.Answerable, "no_answer": v.NoAnswer, "recall_at_5": v.Recall / float64(v.Answerable), "mrr": v.MRR / float64(v.Answerable), "ndcg_at_5": v.NDCG / float64(v.Answerable), "no_answer_false_positive_rate": float64(v.FalsePositive) / float64(v.NoAnswer), "p50_us": v.durations[len(v.durations)/2], "p95_us": v.durations[int(float64(len(v.durations)-1)*.95)], "returned_id_json_bytes": v.ReturnedBytes}
	}
	hash := sha256.Sum256(corpusRaw)
	report := map[string]any{"schema_version": "aevora.retrieval-quality-report/1", "corpus_sha256": hex.EncodeToString(hash[:]), "provenance": corpus.Provenance, "metrics": metrics, "cases": cases, "lexical_policy": retrieval.CoveragePolicy, "semantic": "NOT_RUN_NO_REAL_MODEL_CONFIGURED", "applicability": "NOT_MEASURED_BY_LEXICAL_RANKING", "causal_benefit": "UNKNOWN", "fixture": "SYNTHETIC_PUBLIC_NOT_PRODUCTION"}
	raw, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if dest := os.Getenv(reportEnv); dest != "" {
		f, e := os.OpenFile(dest, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e != nil {
			t.Fatal(e)
		}
		_, e = f.Write(append(raw, '\n'))
		closeErr := f.Close()
		if e != nil || closeErr != nil {
			t.Fatal(e, closeErr)
		}
	}
	brief, _ := json.Marshal(metrics)
	t.Log(string(brief))
}

// Binary relevance, complete relevant set, no duplicate credit. This reduces
// to the original baseline scores when there is exactly one relevant document.
func qualityRanking(ids, relevant []string, k int) (recall, mrr, ndcg float64) {
	wants, seen := map[string]bool{}, map[string]bool{}
	for _, id := range relevant {
		wants[id] = true
	}
	if len(wants) == 0 || k < 1 {
		return
	}
	for i, id := range ids {
		if i >= k {
			break
		}
		if !wants[id] || seen[id] {
			continue
		}
		seen[id] = true
		recall++
		if mrr == 0 {
			mrr = 1 / float64(i+1)
		}
		ndcg += 1 / math.Log2(float64(i+2))
	}
	recall /= float64(len(wants))
	ideal := 0.0
	for i := 0; i < len(wants) && i < k; i++ {
		ideal += 1 / math.Log2(float64(i+2))
	}
	ndcg /= ideal
	return
}

func TestQualityRankingUsesFullRelevantSet(t *testing.T) {
	recall, mrr, ndcg := qualityRanking([]string{"a", "a", "unrelated"}, []string{"a", "b"}, 5)
	if recall != .5 || mrr != 1 || math.Abs(ndcg-1/(1+1/math.Log2(3))) > 1e-9 {
		t.Fatal(recall, mrr, ndcg)
	}
}
