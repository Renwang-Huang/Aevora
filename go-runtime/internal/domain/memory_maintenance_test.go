package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"testing"
)

func TestSourceRevocationWithdrawsDependenciesAndCannotAutoRevive(t *testing.T) {
	ctx := context.Background()
	f := automationTestFixture(t, nil)
	event := taskEvent("source", "turn-a")
	if e := f.store.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		if _, e := r.IngestTaskEvent(ctx, event); e != nil {
			return e
		}
		if e := r.PutEdge(ctx, "DERIVED_FROM", "Candidate", f.id, "ExternalObservation", TaskSourceID(event), nil); e != nil {
			return e
		}
		_, e := r.AutomateCandidate(ctx, f.backend, f.id, f.head, f.policy, f.sourcePolicy, f.root, f.pin)
		return e
	}); e != nil {
		t.Fatal(e)
	}
	if e := f.store.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).RevokeTaskSource(ctx, TaskSourceID(event), "another")
		return e
	}); e == nil {
		t.Fatal("wrong project revoked source")
	}
	if e := f.store.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).RevokeTaskSource(ctx, TaskSourceID(event), "fixture")
		return e
	}); e != nil {
		t.Fatal(e)
	}
	view, e := (Repo{f.store.Read()}).Inspect(ctx, f.id)
	if e != nil || M(view["head"])["state"] != "WITHDRAWN" {
		t.Fatal(view, e)
	}
	if e := f.store.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).AutomateCandidate(ctx, f.backend, f.id, S(view["head_sha256"]), f.policy, f.sourcePolicy, f.root, f.pin)
		return e
	}); e == nil {
		t.Fatal("revoked dependency was republished")
	}
}
