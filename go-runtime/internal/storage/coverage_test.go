package storage

import (
	"context"
	"fmt"
	"testing"
)

func TestCoverageFiltersBeforePaginationAndKeepsPorterMatching(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	if err := s.Write(ctx, func(r *Repository) error {
		// High title weight and a long strategy make the useful record rank
		// below many one-word matches. A post-top-k filter would lose it.
		for i := 0; i < 140; i++ {
			if e := r.PutNode(ctx, "Experience", map[string]any{"id": fmt.Sprintf("experience:decoy:%03d", i), "title": "certificate certificate", "public_summary": "unrelated topic"}); e != nil {
				return e
			}
		}
		return r.PutNode(ctx, "Experience", map[string]any{"id": "experience:useful", "title": "renewal", "public_summary": "renewing certificates after expiration"})
	}); err != nil {
		t.Fatal(err)
	}
	for _, query := range []string{"certificate renew expiry", "renewing certificates"} {
		hits, _, e := s.Read().Recall(ctx, "Experience", query, 1, 0)
		if e != nil || len(hits) != 1 || hits[0].ID != "experience:useful" {
			t.Fatal(query, hits, e)
		}
		if next, _, e := s.Read().Recall(ctx, "Experience", query, 1, 1); e != nil || len(next) != 0 {
			t.Fatal("unstable filtered page", next, e)
		}
	}
	for _, query := range []string{"certificate private key recovery", `missing" OR title:certificate*`} {
		if hits, _, e := s.Read().Recall(ctx, "Experience", query, 5, 0); e != nil || len(hits) != 0 {
			t.Fatal("one shared token or operators admitted unrelated results", query, hits, e)
		}
	}
}
