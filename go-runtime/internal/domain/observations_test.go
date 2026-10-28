package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"strings"
	"testing"
)

func TestObservationSearchIsLiteralPublicAndNeverApplicable(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	platform.PrivateDir(root, true)
	s, err := storage.Open(ctx, filepath.Join(root, "data.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	err = s.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		service := Service{Repo: r, Run: "search-test", Facts: Map{}, NewID: func() string { return "private-reference-marker" }}
		query, err := service.ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		for i, title := range []string{"Host 重启与 MCP 连接", "SQLite 100% backup"} {
			key := []string{"restart", "storage"}[i]
			_, err := r.Propose(ctx, service.Run, Map{"candidate_key": key, "title": title, "strategy": "Investigative lead only", "public_summary": "Unverified observation", "necessary_conditions": Map{}, "scope": Map{}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{"No independent verifier"}, "source_references": []any{Map{"kind": "Query", "id": query["query_id"]}}})
			if err != nil {
				return err
			}
		}
		for text, want := range map[string]int{"重启": 1, "mcp": 1, "100%": 1, "private-reference-marker": 0, "%' OR 1=1 --": 0} {
			result, err := r.SearchObservations(ctx, text, 10)
			if err != nil {
				return err
			}
			if len(A(result["observations"])) != want || result["authority"] != "UNTRUSTED_OBSERVATIONS_ONLY" || result["applicability"] != "NOT_EVALUATED" {
				t.Fatal(text, result)
			}
			encoded, _ := codec.Canonical(result)
			if strings.Contains(string(encoded), "private-reference-marker") && text != "private-reference-marker" {
				t.Fatal("raw source reference leaked")
			}
		}
		service.NewID = nil
		result, err := service.ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		if len(A(result["candidates"])) != 0 {
			t.Fatal("observations entered experience resolver")
		}
		if _, err = service.RecordDecision(ctx, Map{"query_id": query["query_id"], "experience_id": "candidate:search-test:restart", "decision": "APPLY", "reason": "Not an experience"}); err == nil {
			t.Fatal("observation accepted as APPLY experience")
		}
		if _, err = r.SearchObservations(ctx, "", 21); err == nil {
			t.Fatal("search output bound ignored")
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}
