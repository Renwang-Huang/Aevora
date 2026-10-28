package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
	"time"
)

func TestUnscopedDraftIsCapturedButCannotBeAdmittedOrRetrieved(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	platform.PrivateDir(root, true)
	s, err := storage.Open(ctx, filepath.Join(root, "data.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	err = s.Write(ctx, func(repo *storage.Repository) error {
		r := Repo{repo}
		p := Map{"candidate_key": "ui-observation", "title": "Explicit synthetic UI draft", "strategy": "Explain the empty state", "public_summary": "Draft test only", "necessary_conditions": Map{}, "inapplicable_conditions": Map{}, "scope": Map{}, "unknown_fields": []any{}, "limitations": []any{"Scope is not established"}, "source_references": []any{}}
		result, err := r.Propose(ctx, "draft-test", p)
		if err != nil {
			return err
		}
		id := S(result["candidate_id"])
		view, err := r.Inspect(ctx, id)
		if err != nil {
			return err
		}
		if M(view["head"])["state"] != "PROPOSED" {
			t.Fatal("draft was admitted")
		}
		if _, err = r.Admission(ctx, M(view["candidate"]), Map{}); err == nil {
			t.Fatal("unscoped draft admitted")
		}
		grant := ReviewGrant{Principal: "host:test", ExpiresAt: time.Now().Add(time.Minute).UTC().Format(time.RFC3339Nano)}
		if _, err = r.Publish(ctx, id, S(view["head_sha256"]), "publish", "Synthetic guard test", grant); err == nil {
			t.Fatal("draft published")
		}
		query, err := (Service{Repo: r, Run: "draft-test", Facts: Map{}}).ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		if len(A(query["candidates"])) != 0 {
			t.Fatal("draft entered query results")
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}
