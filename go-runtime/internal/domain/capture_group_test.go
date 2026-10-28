package domain

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
	"time"
)

func TestCaptureGroupsSourcesWithoutPromotionOrHidingFeedback(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	db, err := storage.Open(ctx, filepath.Join(root, "graph.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	event := func(project, signal, key string) captureformat.Event {
		e, err := captureformat.New(project, "session-1", "turn-1", "call-"+key, "BASH", signal)
		if err != nil {
			t.Fatal(err)
		}
		return e
	}
	first := event("project-a", "JSON_DECODE_ERROR", "1")
	apply := func(e captureformat.Event) Map {
		t.Helper()
		var out Map
		err := db.Write(ctx, func(raw *storage.Repository) error {
			var e2 error
			out, e2 = (Repo{raw}).IngestCapture(ctx, e.Map())
			return e2
		})
		if err != nil {
			t.Fatal(err)
		}
		return out
	}
	initial := apply(first)
	candidate := S(initial["candidate_id"])
	if initial["authority"] != "EXTERNAL_UNVERIFIED" || initial["outcome"] != "NOT_CREATED" {
		t.Fatal(initial)
	}
	for _, key := range []string{"2", "3", "4", "5", "6", "7", "8"} {
		if got := apply(event("project-a", "JSON_DECODE_ERROR", key)); got["candidate_id"] != candidate {
			t.Fatal("same signal fragmented", got)
		}
	}
	if got := apply(event("project-b", "JSON_DECODE_ERROR", "9")); got["candidate_id"] == candidate {
		t.Fatal("different projects merged", got)
	}
	if got := apply(event("project-a", "PERMISSION_DENIED", "a")); got["candidate_id"] == candidate {
		t.Fatal("different signal merged", got)
	}
	err = db.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		view, e := r.Inspect(ctx, candidate)
		if e != nil {
			return e
		}
		if M(view["head"])["state"] != "PROPOSED" || len(M(M(M(view["candidate"])["body"])["scope"])) != 0 {
			t.Fatal("untrusted signal became scoped", view)
		}
		if _, e = r.Admission(ctx, M(view["candidate"]), Map{}); e == nil {
			t.Fatal("unverified signal admitted")
		}
		_, e = (Service{Repo: r, Run: "consumer-run"}).RecordObservationUse(ctx, Map{"candidate_id": candidate, "report_key": "actual-check", "purpose": "DEBUGGING", "disposition": "INVESTIGATED", "reason": "Compared the signal with actual source"})
		return e
	})
	if err != nil {
		t.Fatal(err)
	}
	result, err := (Repo{db.Read()}).RecallObservations(ctx, "JSONDecodeError", 20)
	if err != nil {
		t.Fatal(err)
	}
	var target Map
	for _, v := range A(result["observations"]) {
		if M(v)["candidate_id"] == candidate {
			target = M(v)
		}
	}
	if target == nil {
		t.Fatal("auto candidate was not searchable", result)
	}
	sources := M(target["capture_sources"])
	feedback := M(target["usage_feedback"])
	if I(sources["source_record_count"]) != 8 || sources["project_hint"] != "project-a" || sources["failure"] != "NOT_PROVEN" {
		t.Fatal("incorrect source accounting", sources)
	}
	if len(A(feedback["reports"])) != 1 || M(A(feedback["reports"])[0])["disposition"] != "INVESTIGATED" {
		t.Fatal("capture records hid usage feedback", feedback)
	}
	literal, err := (Repo{db.Read()}).SearchObservations(ctx, "JSONDecodeError", 20)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, v := range A(literal["observations"]) {
		if row := M(v); row["candidate_id"] == candidate {
			s := M(row["capture_sources"])
			found = I(s["source_record_count"]) == 8 && s["session_ref"] == "session-1" && s["project_authority"] == "UNVERIFIED_HOOK_HINT"
		}
	}
	if !found {
		t.Fatal("literal Console search omitted source locator", literal)
	}
	err = db.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		view, e := r.Inspect(ctx, candidate)
		if e != nil {
			return e
		}
		grant := ReviewGrant{Principal: "host:fixture", ExpiresAt: time.Now().Add(time.Minute).UTC().Format(time.RFC3339Nano)}
		_, e = r.Transition(ctx, candidate, "REJECTED", S(view["head_sha256"]), "reject", "Fixture owner rejection", grant, Map{})
		return e
	})
	if err != nil {
		t.Fatal(err)
	}
	apply(event("project-a", "JSON_DECODE_ERROR", "b"))
	view, err := (Repo{db.Read()}).Inspect(ctx, candidate)
	if err != nil || M(view["head"])["state"] != "REJECTED" {
		t.Fatal("new source revived rejected candidate", view, err)
	}
	later, e2 := captureformat.New("project-a", "session-1", "turn-later", "call-later", "BASH", "JSON_DECODE_ERROR")
	if e2 != nil {
		t.Fatal(e2)
	}
	laterID := S(apply(later)["candidate_id"])
	laterView, e2 := (Repo{db.Read()}).Inspect(ctx, laterID)
	if e2 != nil || laterID == candidate || M(laterView["head"])["state"] != "PROPOSED" {
		t.Fatal("rejection suppressed an independent turn", laterView, e2)
	}
	count, err := db.Read().Count(ctx, "VerifiedOutcome", "")
	if err != nil || count != 0 {
		t.Fatal("capture created verified result", count, err)
	}
}

func TestCaptureSourceAndConsolidationRollbackTogether(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	db, err := storage.Open(ctx, filepath.Join(root, "graph.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	e, err := captureformat.New("fixture", "session-1", "turn-1", "call-f", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	wrong := captureCandidate(e)
	wrong["title"] = "Conflicting immutable candidate"
	err = db.Write(ctx, func(raw *storage.Repository) error {
		_, e2 := (Repo{raw}).Propose(ctx, captureCurrentRun(e), wrong)
		return e2
	})
	if err != nil {
		t.Fatal(err)
	}
	err = db.Write(ctx, func(raw *storage.Repository) error { _, e2 := (Repo{raw}).IngestCapture(ctx, e.Map()); return e2 })
	if !errors.Is(err, ErrConflict) {
		t.Fatal("conflicting consolidation accepted", err)
	}
	value, err := (Repo{db.Read()}).Get(ctx, "ExternalObservation", "external-observation:capture:"+e.ID)
	if err != nil || value != nil {
		t.Fatal("source committed without consolidation", value, err)
	}
}
