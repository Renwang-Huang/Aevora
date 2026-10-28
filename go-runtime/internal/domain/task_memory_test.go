package domain

import (
	"context"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"strings"
	"testing"
)

func TestTaskSourcePagesRespectBytesWithoutDroppingLongSources(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	candidate := ""
	if e := db.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		event := taskEvent("long-0", "turn-a")
		body := Map{"candidate_key": "long-sources", "title": "Long public source fixture", "strategy": "Inspect source claims", "public_summary": "Synthetic transport fixture", "necessary_conditions": Map{}, "scope": Map{}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{}, "source_references": []any{}}
		v, e := r.Propose(ctx, TaskEpisode(event), body)
		if e != nil {
			return e
		}
		candidate = S(v["candidate_id"])
		for i := 0; i < 12; i++ {
			event := taskEvent(fmt.Sprintf("long-%d", i), "turn-a")
			event["summary"] = strings.Repeat("界", 1500)
			if _, e = r.IngestTaskEvent(ctx, event); e != nil {
				return e
			}
			if e = r.PutEdge(ctx, "DERIVED_FROM", "Candidate", candidate, "ExternalObservation", TaskSourceID(event), nil); e != nil {
				return e
			}
		}
		return nil
	}); e != nil {
		t.Fatal(e)
	}
	after := ""
	seen := map[string]bool{}
	pages := 0
	for {
		v, e := (Repo{db.Read()}).TaskCandidateSources(ctx, candidate, after, 20, "fixture")
		if e != nil {
			t.Fatal(e)
		}
		pages++
		for _, value := range A(v["sources"]) {
			id := S(M(value)["observation_id"])
			if seen[id] {
				t.Fatal("source repeated", id)
			}
			seen[id] = true
		}
		if !B(v["more"]) {
			break
		}
		after = S(v["next_cursor"])
		if after == "" || pages > 12 {
			t.Fatal("pagination did not advance", v)
		}
	}
	if len(seen) != 12 || pages < 2 {
		t.Fatal("source lost or budget ignored", len(seen), pages)
	}
}

func taskEvent(item, turn string) Map {
	return Map{"schema_version": TaskEventVersion, "project": "fixture", "task_ref": "repair", "session_ref": "session-a", "turn_ref": turn, "item_ref": item, "kind": "COMMAND", "status": "FAILED", "action": "GO_TEST", "summary": "TestReadMissing failed before the change", "exit_code": 1, "occurred_at": nil, "revision": nil}
}
func taskStore(t *testing.T) *storage.Store {
	t.Helper()
	root := filepath.Join(t.TempDir(), "private")
	if e := platform.PrivateDir(root, true); e != nil {
		t.Fatal(e)
	}
	db, e := storage.Open(context.Background(), filepath.Join(root, "db.sqlite"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { db.Close() })
	return db
}
func TestTaskSourceIdentityPrivacyAndAtomicity(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	e := taskEvent("item-a", "turn-a")
	write := func(event Map) error {
		return db.Write(ctx, func(raw *storage.Repository) error { _, err := (Repo{raw}).IngestTaskEvent(ctx, event); return err })
	}
	if err := write(e); err != nil {
		t.Fatal(err)
	}
	if err := write(e); err != nil {
		t.Fatal(err)
	}
	changed := Clone(e)
	changed["summary"] = "Different claim for same item"
	if write(changed) == nil {
		t.Fatal("conflicting source replaced")
	}
	for _, mutate := range []func(Map){func(p Map) { p["summary"] = "private /home/user/file" }, func(p Map) { p["trusted"] = true }, func(p Map) { p["status"] = "COMPLETED" }, func(p Map) { p["project"] = "../other" }} {
		p := Clone(e)
		mutate(p)
		if ValidateTaskEvent(p) == nil {
			t.Fatal("invalid event accepted", p)
		}
	}
	other := taskEvent("item-a", "turn-b")
	if TaskSourceID(e) == TaskSourceID(other) || TaskEpisode(e) != TaskEpisode(other) {
		t.Fatal("turn or task identity broken")
	}
	other["session_ref"] = "session-b"
	if TaskEpisode(e) == TaskEpisode(other) {
		t.Fatal("sessions merged")
	}
	other["item_ref"] = "rollback"
	err := db.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).IngestTaskEvent(ctx, other)
		if e != nil {
			return e
		}
		return ErrConflict
	})
	if err == nil {
		t.Fatal("rollback accepted")
	}
	if p, _ := db.Read().Get(ctx, "ExternalObservation", TaskSourceID(other)); p != nil {
		t.Fatal("rolled back source retained")
	}
	if n, _ := db.Read().Count(ctx, "VerifiedOutcome", ""); n != 0 {
		t.Fatal("observation minted outcome")
	}
}
func TestTaskSourceReadIsPagedAndProjectScoped(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	candidate := ""
	if err := db.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		events := []Map{taskEvent("item-z", "turn-a"), taskEvent("item-a", "turn-b"), taskEvent("item-c", "turn-b")}
		p := Map{"candidate_key": "summary", "title": "Task summary", "strategy": "Read the sources before reuse", "public_summary": "Synthetic task source fixture", "necessary_conditions": Map{}, "scope": Map{}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{}, "source_references": []any{}}
		v, e := r.Propose(ctx, TaskEpisode(events[0]), p)
		if e != nil {
			return e
		}
		candidate = S(v["candidate_id"])
		for _, event := range events {
			if _, e = r.IngestTaskEvent(ctx, event); e != nil {
				return e
			}
			if e = r.PutEdge(ctx, "DERIVED_FROM", "Candidate", candidate, "ExternalObservation", TaskSourceID(event), nil); e != nil {
				return e
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	service := Service{Repo: Repo{db.Read()}, Run: "consumer", Facts: Map{"target_project": "fixture"}}
	first, e := service.ReadObservationSources(ctx, candidate, "", 2)
	if e != nil || len(A(first["sources"])) != 2 || first["more"] != true {
		t.Fatal(first, e)
	}
	last, e := service.ReadObservationSources(ctx, candidate, S(first["next_cursor"]), 2)
	if e != nil || len(A(last["sources"])) != 1 || last["more"] != false {
		t.Fatal(last, e)
	}
	for _, facts := range []Map{{}, {"target_project": "another"}} {
		service.Facts = facts
		if _, e = service.ReadObservationSources(ctx, candidate, "", 2); e == nil {
			t.Fatal("cross project or unknown project read accepted")
		}
	}
}
