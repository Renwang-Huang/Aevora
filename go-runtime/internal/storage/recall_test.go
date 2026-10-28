package storage

import (
	"context"
	"errors"
	"fmt"
	"testing"
)

func TestRecallUsesFTSAndRebuildsWithoutChangingGraphFormat(t *testing.T) {
	s := database(t)
	ctx := context.Background()
	if err := s.Write(ctx, func(r *Repository) error {
		for i := 0; i < 320; i++ {
			if err := r.PutNode(ctx, "Experience", map[string]any{"id": fmt.Sprintf("experience:%03d", i), "title": "Storage backup", "public_summary": "Unrelated disk maintenance", "strategy": "Take a backup"}); err != nil {
				return err
			}
		}
		return r.PutNode(ctx, "Experience", map[string]any{"id": "experience:queue", "title": "Native queued instructions", "public_summary": "Use the native queue for a running session", "strategy": "Queue a message", "private_reference": "do-not-search-this-marker"})
	}); err != nil {
		t.Fatal(err)
	}
	for _, query := range []string{"native queue", "原生队列", "queued instruction"} {
		hits, _, err := s.Read().Recall(ctx, "Experience", query, 5, 0)
		if err != nil || len(hits) != 1 || hits[0].ID != "experience:queue" {
			t.Fatalf("%s: %v %v", query, hits, err)
		}
	}
	if hits, _, err := s.Read().Recall(ctx, "Experience", "do-not-search-this-marker", 5, 0); err != nil || len(hits) != 0 {
		t.Fatal("private field indexed", hits, err)
	}
	if err := checkDDL(ctx, s.writer); err != nil {
		t.Fatal("derived index changed graph schema", err)
	}
	if _, err := s.writer.ExecContext(ctx, "DROP TRIGGER temp.aevora_recall_insert; DROP TABLE temp.aevora_recall"); err != nil {
		t.Fatal(err)
	}
	if hits, _, err := s.Read().Recall(ctx, "Experience", "native queue", 5, 0); err != nil || len(hits) != 1 {
		t.Fatal("index did not rebuild", hits, err)
	}
	stop := errors.New("rollback")
	if err := s.Write(ctx, func(r *Repository) error {
		if err := r.PutNode(ctx, "Candidate", map[string]any{"id": "candidate:rollback", "body": map[string]any{"title": "Phantom indexing"}}); err != nil {
			return err
		}
		return stop
	}); !errors.Is(err, stop) {
		t.Fatal(err)
	}
	if hits, _, err := s.Read().Recall(ctx, "Candidate", "phantom", 5, 0); err != nil || len(hits) != 0 {
		t.Fatal("rolled-back source leaked into index", hits, err)
	}
}
