package domain

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
)

func TestObservationUseIsDurableIdempotentAndUntrusted(t *testing.T) {
	ctx := context.Background()
	dir := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(dir, true); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "db.sqlite")
	db, err := storage.Open(ctx, path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	var candidateID, reportID string
	err = db.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		body := Map{"candidate_key": "missing-task-lookup-regression", "title": "Investigative lead", "strategy": "Inspect source", "public_summary": "Fixture", "necessary_conditions": Map{}, "scope": Map{}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{}, "source_references": []any{}}
		candidate, e := r.Propose(ctx, "task-11111111-2222-3333-4444-555555555555", body)
		if e != nil {
			return e
		}
		candidateID = S(candidate["candidate_id"])
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	input := Map{"candidate_id": candidateID, "report_key": "stablekey", "purpose": "DEBUGGING", "disposition": "INVESTIGATED", "reason": "Compared with current source", "elapsed_seconds": 45}
	call := func(report Map) (Map, error) {
		var result Map
		err := db.Write(ctx, func(raw *storage.Repository) error {
			var e error
			result, e = (Service{Repo: Repo{raw}, Run: "user-run"}).RecordObservationUse(ctx, report)
			return e
		})
		return result, err
	}
	first, err := call(input)
	if err != nil || first["exposure"] != "NOT_VERIFIED" || first["adoption"] != "CLAIM_ONLY" || first["trusted_outcome"] != "NOT_CREATED" || first["idempotent_replay"] != false {
		t.Fatal(first, err)
	}
	reportID = S(first["report_id"])
	repeated, err := call(input)
	if err != nil || repeated["report_id"] != reportID || repeated["idempotent_replay"] != true {
		t.Fatal(repeated, err)
	}
	changed := Clone(input)
	changed["disposition"] = "REUSED"
	if _, err = call(changed); !errors.Is(err, ErrConflict) {
		t.Fatal("key reused for changed claim", err)
	}
	for _, invalid := range []Map{
		{"candidate_id": "candidate:missing", "report_key": "missing", "purpose": "OTHER", "disposition": "REUSED", "reason": "No candidate"},
		{"candidate_id": candidateID, "report_key": "secret", "purpose": "OTHER", "disposition": "REUSED", "reason": "/home/private/location"},
		{"candidate_id": candidateID, "report_key": "verdict", "purpose": "OTHER", "disposition": "REUSED", "reason": "Unsupported assertion", "verified": true},
	} {
		if _, err = call(invalid); err == nil {
			t.Fatal("invalid report accepted", invalid)
		}
	}
	if err = db.Close(); err != nil {
		t.Fatal(err)
	}
	db, err = storage.Open(ctx, path, storage.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	p, err := (Repo{db.Read()}).Required(ctx, "ExternalObservation", reportID)
	if err != nil || p["record_kind"] != "OBSERVATION_USE_CLAIM" || p["candidate_id"] != candidateID || p["authority"] != "EXTERNAL_UNVERIFIED" {
		t.Fatal(p, err)
	}
	if _, err = call(input); err != nil {
		t.Fatal("replay after restart", err)
	}
	if err = (Repo{db.Read()}).RequireEdge(ctx, "DERIVED_FROM", "ExternalObservation", reportID, "Candidate", candidateID); err != nil {
		t.Fatal("missing provenance edge", err)
	}
	search, err := (Repo{db.Read()}).RecallObservations(ctx, "investigative lead", 5)
	if err != nil || len(A(search["observations"])) != 1 {
		t.Fatal("next task could not find observation", search, err)
	}
	feedback := M(M(A(search["observations"])[0])["usage_feedback"])
	if len(A(feedback["reports"])) != 1 || M(A(feedback["reports"])[0])["disposition"] != "INVESTIGATED" || feedback["exposure"] != "NOT_VERIFIED" {
		t.Fatal("next search did not disclose untrusted use feedback", feedback)
	}
	outcomes, err := db.Read().List(ctx, "VerifiedOutcome", storage.Filter{Run: "user-run", Limit: 10})
	if err != nil || len(outcomes) != 0 {
		t.Fatal("claim became trusted outcome", outcomes, err)
	}
}
