package domain

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"
)

// Audit records provide an append-only job ledger without changing graph DDL.
// Fixed-width sequence IDs are a fence, independent of wall-clock ordering.
func MemoryJobID(source string) string { return "memory-job:" + H([]any{"task-summary/1", source}) }
func (r Repo) MemoryJobState(ctx context.Context, job string) (Map, error) {
	rows, err := r.Repository.AuditPrefix(ctx, job+":", 1, true)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, nil
	}
	p := rows[0]
	if p["job_id"] != job || p["event"] != "MEMORY_JOB" {
		return nil, ErrConflict
	}
	return p, nil
}
func (r Repo) appendMemoryJob(ctx context.Context, p Map) error {
	p = Clone(p)
	p["id"] = fmt.Sprintf("%s:%06d", S(p["job_id"]), I(p["sequence"]))
	p["event"] = "MEMORY_JOB"
	p["schema_version"] = "aevora.memory-job/1"
	return r.Put(ctx, "AuditEvent", p)
}
func (r Repo) EnqueueMemoryJob(ctx context.Context, source string) error {
	p, err := r.Required(ctx, "ExternalObservation", source)
	if err != nil || p["record_kind"] != TaskEventKind {
		return ErrInvalid
	}
	job := MemoryJobID(source)
	old, err := r.MemoryJobState(ctx, job)
	if err != nil || old != nil {
		return err
	}
	return r.appendMemoryJob(ctx, Map{"job_id": job, "source_id": source, "run_id": p["run_id"], "project": M(p["event"])["project"], "sequence": 0, "state": "PENDING", "attempts": 0, "worker": "", "until": nil, "created_at": Now(), "candidate_id": "", "reason": "WAITING_FOR_WORKER"})
}

func (r Repo) MemorySnapshot(ctx context.Context, job string) (Map, error) {
	state, e := r.MemoryJobState(ctx, job)
	if e != nil || state == nil {
		return nil, ErrInvalid
	}
	sources, e := r.TaskSources(ctx, S(state["run_id"]))
	if e != nil {
		return nil, e
	}
	if len(sources) >= 128 {
		return nil, ErrInvalid
	}
	active := []Map{}
	for _, source := range sources {
		revoked, e := r.TaskSourceRevoked(ctx, S(source["id"]))
		if e != nil {
			return nil, e
		}
		if revoked {
			continue
		}
		active = append(active, source)
		if ValidateRecord("ExternalObservation", source) != nil || M(source["event"])["project"] != state["project"] {
			return nil, ErrConflict
		}
	}
	items := []any{}
	for _, source := range active {
		items = append(items, source)
	}
	return Map{"sources": items, "input_sha256": H(items), "project": state["project"], "episode_id": state["run_id"]}, nil
}

// SummarizeTask is deterministic compression of reported engineering content.
// It neither infers root causes nor upgrades a command result to a verified outcome.
func SummarizeTask(snapshot Map) (Map, string, error) {
	sources, ok := snapshot["sources"].([]any)
	if !ok {
		return nil, "", ErrInvalid
	}
	failure, change, check := false, false, false
	notes := []string{}
	seen := map[string]bool{}
	for _, value := range sources {
		source := M(value)
		e := M(source["event"])
		if e["status"] == "FAILED" {
			failure = true
		}
		if e["kind"] == "CHANGE" && e["status"] == "COMPLETED" {
			change = true
		}
		if (e["kind"] == "CHECK" || stringSet("GO_TEST PYTEST NPM_TEST")[S(e["action"])]) && e["status"] == "COMPLETED" && e["exit_code"] != nil && I(e["exit_code"]) == 0 {
			check = true
		}
		note := S(e["summary"])
		if !seen[note] && len(notes) < 8 {
			notes = append(notes, note)
			seen[note] = true
		}
	}
	if !failure || !change || !check {
		return nil, "MORE_ENGINEERING_EVIDENCE_REQUIRED", nil
	}
	strategy := "Review these reported engineering steps and independently repeat the relevant checks before reuse: " + strings.Join(notes, "; ")
	if runes := []rune(strategy); len(runes) > 3000 {
		strategy = string(runes[:3000])
	}
	if !publicText(strategy, 4000) {
		return nil, "SUMMARY_BUDGET_EXCEEDED", nil
	}
	body := Map{"candidate_key": "summary-" + S(snapshot["input_sha256"])[:16], "title": "Engineering task evidence: " + S(snapshot["project"]), "strategy": strategy, "public_summary": "Reported failure, completed change and successful check are associated with one task. Source ordering, root cause, adoption and benefit remain unverified.", "necessary_conditions": Map{"target_project": []any{snapshot["project"]}}, "scope": Map{"target_project": []any{snapshot["project"]}}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{"Source association is not proof of causation or chronological order.", "Runtime item results are not independent verification receipts.", "Revision and worktree applicability require independent verification."}, "source_references": []any{}}
	return body, "CANDIDATE_READY", ValidateProposal(body)
}
func (r Repo) MemoryFinish(ctx context.Context, job, worker string, fence int, input string, now time.Time) (Map, error) {
	state, e := r.MemoryJobState(ctx, job)
	if e != nil || state == nil || state["state"] != "RUNNING" || state["worker"] != worker || I(state["sequence"]) != fence {
		return nil, ErrConflict
	}
	end, e := timestamp(state["until"])
	if e != nil || !now.Before(end) {
		return nil, ErrConflict
	}
	snapshot, e := r.MemorySnapshot(ctx, job)
	if e != nil {
		return nil, e
	}
	next := Clone(state)
	next["sequence"] = fence + 1
	next["until"] = nil
	if snapshot["input_sha256"] != input {
		next["state"] = "RETRY"
		next["reason"] = "SOURCE_SET_CHANGED"
		next["until"] = now.Add(time.Second).UTC().Format(time.RFC3339Nano)
		if e = r.appendMemoryJob(ctx, next); e != nil {
			return nil, e
		}
		return Map{"status": "RETRY", "reason": next["reason"]}, nil
	}
	body, reason, e := SummarizeTask(snapshot)
	if e != nil {
		return nil, e
	}
	next["state"] = "COMPLETED"
	next["reason"] = reason
	next["input_sha256"] = input
	if body != nil {
		result, e := r.Propose(ctx, S(snapshot["episode_id"]), body)
		if e != nil {
			return nil, e
		}
		next["candidate_id"] = result["candidate_id"]
		for _, value := range A(snapshot["sources"]) {
			source := M(value)
			if e = r.PutEdge(ctx, "DERIVED_FROM", "Candidate", S(result["candidate_id"]), "ExternalObservation", S(source["id"]), nil); e != nil {
				return nil, e
			}
		}
	}
	if e = r.appendMemoryJob(ctx, next); e != nil {
		return nil, e
	}
	return Map{"status": "COMPLETED", "reason": reason, "candidate_id": next["candidate_id"], "publication": "NOT_PUBLISHED"}, nil
}
func (r Repo) ProcessMemoryJobs(ctx context.Context, project string, limit int) (Map, error) {
	jobs, e := r.Repository.ReadyMemoryJobs(ctx, project, limit, time.Now().UTC().Format(time.RFC3339Nano))
	if e != nil {
		return nil, e
	}
	results := []any{}
	for _, job := range jobs {
		worker := "builtin-task-summary"
		state, e := r.MemoryClaim(ctx, S(job["job_id"]), worker, time.Now())
		if e != nil {
			return nil, e
		}
		if state["state"] == "QUARANTINED" {
			results = append(results, Map{"status": "QUARANTINED"})
			continue
		}
		snapshot, e := r.MemorySnapshot(ctx, S(job["job_id"]))
		if errors.Is(e, ErrInvalid) {
			failed := Clone(state)
			failed["sequence"] = I(state["sequence"]) + 1
			failed["state"] = "QUARANTINED"
			failed["until"] = nil
			failed["reason"] = "SOURCE_SNAPSHOT_LIMIT_OR_INVALID"
			if e = r.appendMemoryJob(ctx, failed); e != nil {
				return nil, e
			}
			results = append(results, Map{"status": "QUARANTINED", "reason": failed["reason"]})
			continue
		}
		if e != nil {
			return nil, e
		}
		result, e := r.MemoryFinish(ctx, S(job["job_id"]), worker, I(state["sequence"]), S(snapshot["input_sha256"]), time.Now())
		if e != nil {
			return nil, e
		}
		results = append(results, result)
	}
	return Map{"results": results, "processed": len(results), "extractor": "task-summary/1", "outcome": "NOT_CREATED"}, nil
}
func (r Repo) MemoryClaim(ctx context.Context, job, worker string, now time.Time) (Map, error) {
	if !validLocal(worker, 96) || !strings.HasPrefix(job, "memory-job:") {
		return nil, ErrInvalid
	}
	old, err := r.MemoryJobState(ctx, job)
	if err != nil || old == nil {
		return nil, ErrInvalid
	}
	state := S(old["state"])
	if state == "COMPLETED" || state == "QUARANTINED" {
		return nil, ErrConflict
	}
	if old["until"] != nil {
		end, err := timestamp(old["until"])
		if err != nil {
			return nil, err
		}
		if now.Before(end) {
			return nil, ErrConflict
		}
	}
	p := Clone(old)
	p["sequence"] = I(old["sequence"]) + 1
	p["attempts"] = I(old["attempts"]) + 1
	p["worker"] = worker
	p["state"] = "RUNNING"
	p["until"] = now.Add(30 * time.Second).UTC().Format(time.RFC3339Nano)
	if I(p["attempts"]) > 3 {
		p["state"] = "QUARANTINED"
		p["reason"] = "RETRY_BUDGET_EXHAUSTED"
	}
	if err = r.appendMemoryJob(ctx, p); err != nil {
		return nil, err
	}
	return p, nil
}

func ValidMemoryLimit(v any) bool { return boundedInteger(v, 16) && I(v) > 0 }

func (r Repo) TaskSources(ctx context.Context, run string) ([]Map, error) {
	return r.Repository.ExternalByKind(ctx, "", run, TaskEventKind, 128)
}
