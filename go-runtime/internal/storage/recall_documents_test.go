package storage

import (
	"context"
	"fmt"
	"strings"
	"testing"
)

func TestSemanticCorpusProjectionIsBoundedPublicAndFiltersWithdrawn(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	if err := s.Write(ctx, func(r *Repository) error {
		for i := 0; i < 330; i++ {
			if e := r.PutNode(ctx, "Experience", map[string]any{"id": fmt.Sprintf("experience:%03d", i), "title": "Public title", "strategy": "Public strategy", "private": "never-send"}); e != nil {
				return e
			}
		}
		if e := r.PutNode(ctx, "Experience", map[string]any{"id": "experience:withdrawn", "title": "withdrawn", "publication_candidate_id": "candidate:w"}); e != nil {
			return e
		}
		return r.PutNode(ctx, "LifecycleHead", map[string]any{"id": "head:w", "candidate_id": "candidate:w", "state": "WITHDRAWN"})
	}); err != nil {
		t.Fatal(err)
	}
	docs, more, err := s.Read().RecallDocuments(ctx, "Experience", 300)
	if err != nil || len(docs) != 300 || !more {
		t.Fatal(len(docs), more, err)
	}
	docs, more, err = s.Read().RecallDocuments(ctx, "Experience", 400)
	if err != nil || len(docs) != 330 || more {
		t.Fatal(len(docs), more, err)
	}
	for _, d := range docs {
		if strings.Contains(d.Text, "never-send") || d.ID == "experience:withdrawn" {
			t.Fatal("private/withdrawn projection", d)
		}
	}
	n, err := s.Read().AvailableExperienceCount(ctx)
	if err != nil || n != 330 {
		t.Fatal("inventory retained old capacity or changed withdrawal semantics", n, err)
	}
}
