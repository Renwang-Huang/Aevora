package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"testing"
	"time"
)

func seedTaskSources(t *testing.T, db *storage.Store) []Map {
	t.Helper()
	ctx := context.Background()
	events := []Map{taskEvent("failure", "turn-a"), taskEvent("change", "turn-b"), taskEvent("check", "turn-b")}
	events[1]["kind"] = "CHANGE"
	events[1]["action"] = "FILE_CHANGE"
	events[1]["status"] = "COMPLETED"
	events[1]["exit_code"] = nil
	events[1]["summary"] = "Keep missing task reads free of directory creation"
	events[2]["kind"] = "CHECK"
	events[2]["status"] = "COMPLETED"
	events[2]["exit_code"] = 0
	events[2]["summary"] = "TestReadMissing passed after the change"
	for _, e := range events {
		if err := db.Write(ctx, func(raw *storage.Repository) error { _, err := (Repo{raw}).IngestTaskEvent(ctx, e); return err }); err != nil {
			t.Fatal(err)
		}
	}
	return events
}
func TestMemoryJobFenceLateSourceAndAtomicResult(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	events := seedTaskSources(t, db)
	job := MemoryJobID(TaskSourceID(events[0]))
	var claim, snapshot Map
	write := func(fn func(Repo) error) error {
		return db.Write(ctx, func(raw *storage.Repository) error { return fn(Repo{raw}) })
	}
	if err := write(func(r Repo) error {
		var e error
		claim, e = r.MemoryClaim(ctx, job, "worker-a", time.Now())
		if e != nil {
			return e
		}
		snapshot, e = r.MemorySnapshot(ctx, job)
		return e
	}); err != nil {
		t.Fatal(err)
	}
	late := taskEvent("late-source", "turn-a")
	late["kind"] = "NOTE"
	late["action"] = "NOTE"
	late["status"] = "UNKNOWN"
	late["exit_code"] = nil
	if err := write(func(r Repo) error { _, e := r.IngestTaskEvent(ctx, late); return e }); err != nil {
		t.Fatal(err)
	}
	var result Map
	if err := write(func(r Repo) error {
		var e error
		result, e = r.MemoryFinish(ctx, job, "worker-a", I(claim["sequence"]), S(snapshot["input_sha256"]), time.Now())
		return e
	}); err != nil || result["status"] != "RETRY" {
		t.Fatal(result, err)
	}
	if err := write(func(r Repo) error {
		_, e := r.MemoryFinish(ctx, job, "worker-a", I(claim["sequence"]), S(snapshot["input_sha256"]), time.Now())
		return e
	}); err == nil {
		t.Fatal("old fence wrote")
	}
	// A simulated crash after all result writes rolls the entire transaction back.
	if err := write(func(r Repo) error {
		if _, e := r.ProcessMemoryJobs(ctx, "fixture", 8); e != nil {
			return e
		}
		return ErrConflict
	}); err == nil {
		t.Fatal("rollback absent")
	}
	if n, _ := db.Read().Count(ctx, "Candidate", ""); n != 0 {
		t.Fatal("partial result survived")
	}
	if err := write(func(r Repo) error { _, e := r.ProcessMemoryJobs(ctx, "fixture", 8); return e }); err != nil {
		t.Fatal(err)
	}
	if n, _ := db.Read().Count(ctx, "Candidate", ""); n != 1 {
		t.Fatal("same source set produced duplicate candidates", n)
	}
	if n, _ := db.Read().Count(ctx, "VerifiedOutcome", ""); n != 0 {
		t.Fatal("summary promoted self-test")
	}
	jobs, e := db.Read().ReadyMemoryJobs(ctx, "another", 16, time.Now().Format(time.RFC3339Nano))
	if e != nil || len(jobs) != 0 {
		t.Fatal("project queue crossed", jobs, e)
	}
}
func TestMemoryLeaseRecoveryRejectsLateWorkerAndCapsAttempts(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	events := seedTaskSources(t, db)
	job := MemoryJobID(TaskSourceID(events[0]))
	now := time.Now()
	var first Map
	write := func(fn func(Repo) error) error {
		return db.Write(ctx, func(raw *storage.Repository) error { return fn(Repo{raw}) })
	}
	if e := write(func(r Repo) error { var e error; first, e = r.MemoryClaim(ctx, job, "old-worker", now); return e }); e != nil {
		t.Fatal(e)
	}
	if e := write(func(r Repo) error { _, e := r.MemoryClaim(ctx, job, "other", now); return e }); e == nil {
		t.Fatal("active lease stolen")
	}
	for i := 1; i <= 3; i++ {
		var state Map
		if e := write(func(r Repo) error {
			var e error
			state, e = r.MemoryClaim(ctx, job, "new-worker", now.Add(time.Duration(i)*31*time.Second))
			return e
		}); e != nil {
			t.Fatal(e)
		}
		if i == 3 && state["state"] != "QUARANTINED" {
			t.Fatal("retry budget ignored", state)
		}
	}
	if e := write(func(r Repo) error {
		_, e := r.MemoryFinish(ctx, job, "old-worker", I(first["sequence"]), "irrelevant", now)
		return e
	}); e == nil {
		t.Fatal("expired worker committed")
	}
}

func TestMemoryOverviewSeparatesProcessedJobsFromCandidateLifecycle(t *testing.T) {
	ctx := context.Background()
	db := taskStore(t)
	events := seedTaskSources(t, db)
	if e := db.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).ProcessMemoryJobs(ctx, "fixture", 8)
		return e
	}); e != nil {
		t.Fatal(e)
	}
	before, e := db.Read().MemoryOverview(ctx, "fixture")
	if e != nil {
		t.Fatal(e)
	}
	for _, v := range A(before["jobs"]) {
		job := M(v)
		if job["state"] != "COMPLETED" || job["candidate_state"] != "PROPOSED" {
			t.Fatal(job)
		}
	}
	if e = db.Write(ctx, func(raw *storage.Repository) error {
		_, e := (Repo{raw}).RevokeTaskSource(ctx, TaskSourceID(events[0]), "fixture")
		return e
	}); e != nil {
		t.Fatal(e)
	}
	after, e := db.Read().MemoryOverview(ctx, "fixture")
	if e != nil {
		t.Fatal(e)
	}
	for _, v := range A(after["jobs"]) {
		job := M(v)
		if job["state"] != "COMPLETED" || job["candidate_state"] != "REJECTED" {
			t.Fatal("job completion hid lifecycle change", job)
		}
	}
}
