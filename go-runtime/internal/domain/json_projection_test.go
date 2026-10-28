package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"strings"
	"testing"
)

func TestJSONVerificationDoesNotPromoteReportedRepairNarratives(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	events := seedTaskSources(t, db)
	var original, derived Map
	e := db.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		if _, e := r.ProcessMemoryJobs(ctx, "fixture", 8); e != nil {
			return e
		}
		rows, e := r.List(ctx, "Candidate", storage.Filter{Limit: 10})
		if e != nil {
			return e
		}
		original = rows[0]
		args := Map{"candidate_id": original["id"], "project": "fixture", "suite_sha256": strings.Repeat("a", 64), "evaluator_sha256": strings.Repeat("b", 64), "source_policy_sha256": strings.Repeat("c", 64), "automation_policy_sha256": strings.Repeat("d", 64), "required_tests": []any{"json_contract::has_source_reader"}}
		v, e := r.JSONCheckProjection(ctx, args, true)
		if e != nil {
			return e
		}
		derived = M(v["candidate"])
		return nil
	})
	if e != nil {
		t.Fatal(e)
	}
	if derived["id"] == original["id"] || strings.Contains(S(M(derived["body"])["strategy"]), S(events[1]["summary"])) || M(derived["body"])["derived_from_candidate_id"] != original["id"] {
		t.Fatal("untrusted narrative was certified", derived)
	}
	after, e := (Repo{db.Read()}).Required(ctx, "Candidate", S(original["id"]))
	if e != nil || after["body_sha256"] != original["body_sha256"] {
		t.Fatal("original observation rewritten", e)
	}
	if e = db.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).RevokeTaskSource(ctx, TaskSourceID(events[0]), "fixture")
		return e
	}); e != nil {
		t.Fatal(e)
	}
	view, e := (Repo{db.Read()}).Inspect(ctx, S(derived["id"]))
	if e != nil || M(view["head"])["state"] != "REJECTED" {
		t.Fatal("projection lost source dependencies", view, e)
	}
}
