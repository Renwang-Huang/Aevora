package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"strings"
)

const TaskEventVersion = "aevora.task-event/1"
const TaskEventKind = "ENGINEERING_TASK_EVENT"

// TaskEvent is a public observation, never a source-verification receipt.
// Project is selected by the trusted local adapter; other event fields remain claims.
func ValidateTaskEvent(e Map) error {
	if !exact(e, "schema_version project task_ref session_ref turn_ref item_ref kind status action summary exit_code occurred_at revision") || e["schema_version"] != TaskEventVersion {
		return ErrInvalid
	}
	for _, k := range []string{"project", "task_ref", "session_ref", "turn_ref", "item_ref"} {
		if !validLocal(S(e[k]), 96) || sensitive.MatchString(S(e[k])) {
			return ErrInvalid
		}
	}
	if !stringSet("COMMAND CHANGE CHECK NOTE")[S(e["kind"])] || !stringSet("COMPLETED FAILED DECLINED UNKNOWN")[S(e["status"])] || !stringSet("GO_TEST PYTEST NPM_TEST COMMAND FILE_CHANGE CHECK NOTE")[S(e["action"])] || !publicText(e["summary"], 1500) {
		return ErrInvalid
	}
	if e["exit_code"] != nil {
		if !boundedInteger(e["exit_code"], 255) || S(e["kind"]) == "CHANGE" || S(e["status"]) == "DECLINED" {
			return ErrInvalid
		}
		if (e["status"] == "COMPLETED" && I(e["exit_code"]) != 0) || (e["status"] == "FAILED" && I(e["exit_code"]) == 0) {
			return ErrInvalid
		}
	}
	if e["occurred_at"] != nil {
		if _, err := timestamp(e["occurred_at"]); err != nil {
			return err
		}
	}
	if e["revision"] != nil && !shaPattern.MatchString(S(e["revision"])) && len(S(e["revision"])) != 40 {
		return ErrInvalid
	}
	if e["revision"] != nil {
		for _, c := range S(e["revision"]) {
			if !strings.ContainsRune("0123456789abcdef", c) {
				return ErrInvalid
			}
		}
	}
	return nil
}
func TaskEpisode(e Map) string {
	return "task-episode-" + H([]any{e["project"], e["task_ref"], e["session_ref"]})[:24]
}
func TaskSourceID(e Map) string {
	return "external-observation:task:" + H([]any{e["project"], e["task_ref"], e["session_ref"], e["turn_ref"], e["item_ref"]})
}

func (r Repo) IngestTaskEvent(ctx context.Context, e Map) (Map, error) {
	if err := ValidateTaskEvent(e); err != nil {
		return nil, err
	}
	id, run := TaskSourceID(e), TaskEpisode(e)
	old, err := r.Get(ctx, "ExternalObservation", id)
	if err != nil {
		return nil, err
	}
	if old != nil {
		if ValidateRecord("ExternalObservation", old) != nil || old["source_sha256"] != H(e) {
			return nil, ErrConflict
		}
		return Map{"status": "RECORDED_UNTRUSTED", "source_id": id, "episode_id": run, "idempotent_replay": true}, nil
	}
	p := Map{"id": id, "run_id": run, "record_kind": TaskEventKind, "status": "UNTRUSTED_TASK_OBSERVATION", "authority": "EXTERNAL_UNVERIFIED", "trusted_outcome": "NOT_CREATED", "created_at": Now(), "source_sha256": H(e), "event": e, "public_summary": e["summary"]}
	if err = r.Put(ctx, "ExternalObservation", p); err != nil {
		return nil, err
	}
	if err = r.EnqueueMemoryJob(ctx, id); err != nil {
		return nil, err
	}
	return Map{"status": "RECORDED_UNTRUSTED", "source_id": id, "episode_id": run, "idempotent_replay": false, "outcome": "NOT_CREATED"}, nil
}
func validateTaskSource(p Map) error {
	if !exact(p, "id run_id record_kind status authority trusted_outcome created_at source_sha256 event public_summary") || p["status"] != "UNTRUSTED_TASK_OBSERVATION" {
		return ErrInvalid
	}
	e := M(p["event"])
	if ValidateTaskEvent(e) != nil || p["id"] != TaskSourceID(e) || p["run_id"] != TaskEpisode(e) || p["source_sha256"] != H(e) || p["public_summary"] != e["summary"] {
		return ErrConflict
	}
	_, err := timestamp(p["created_at"])
	return err
}

// Candidate source reads are authorized against pinned target facts, not a caller project.
func (s Service) ReadObservationSources(ctx context.Context, id, after string, limit int) (Map, error) {
	if limit < 1 || limit > 20 {
		return nil, ErrInvalid
	}
	p, err := s.Repo.Required(ctx, "Candidate", id)
	if err != nil {
		return nil, err
	}
	run := S(p["run_id"])
	if strings.HasPrefix(run, "task-episode-") {
		return s.Repo.TaskCandidateSources(ctx, id, after, limit, S(s.Facts["target_project"]))
	}
	summary, err := s.Repo.CaptureSummary(ctx, id, run)
	if err != nil {
		return nil, err
	}
	if summary != nil {
		if S(s.Facts["target_project"]) == "" || summary["project_hint"] != s.Facts["target_project"] {
			return nil, ErrInvalid
		}
		return s.Repo.CaptureSources(ctx, id, after, limit)
	}
	if run != s.Run {
		return nil, ErrInvalid
	}
	return Map{"candidate_id": id, "sources": []any{}, "more": false, "next_cursor": "", "authority": "UNTRUSTED_SOURCES_ONLY", "reason": "NO_STRUCTURED_SOURCES"}, nil
}
func (r Repo) TaskCandidateSources(ctx context.Context, id, after string, limit int, project string) (Map, error) {
	if project == "" || limit < 1 || limit > 50 || (after != "" && !strings.HasPrefix(after, "external-observation:task:")) {
		return nil, ErrInvalid
	}
	p, err := r.Required(ctx, "Candidate", id)
	if err != nil {
		return nil, err
	}
	links, err := r.Edges(ctx, "Candidate", id, "DERIVED_FROM", false)
	if err != nil {
		return nil, err
	}
	items := []any{}
	more := false
	next := ""
	for _, link := range links {
		if link.TargetLabel != "ExternalObservation" {
			continue
		}
		source, err := r.Required(ctx, "ExternalObservation", link.TargetID)
		if err != nil {
			return nil, err
		}
		if source["record_kind"] != TaskEventKind {
			continue
		}
		if ValidateRecord("ExternalObservation", source) != nil || source["run_id"] != p["run_id"] {
			return nil, ErrConflict
		}
		if M(source["event"])["project"] != project {
			return nil, ErrInvalid
		}
	}
	// Page source identities, not edge hashes; no later job may use this as ingestion progress.
	rows, err := r.Repository.TaskSourceLinks(ctx, id, after, limit+1)
	if err != nil {
		return nil, err
	}
	if len(rows) > limit {
		more = true
		rows = rows[:limit]
	}
	for _, source := range rows {
		if ValidateRecord("ExternalObservation", source) != nil || M(source["event"])["project"] != project {
			return nil, ErrConflict
		}
		items = append(items, Map{"observation_id": source["id"], "event": source["event"], "recorded_at": source["created_at"], "authority": "UNTRUSTED_TASK_OBSERVATION"})
		preview := Map{"candidate_id": id, "episode_id": p["run_id"], "sources": items, "next_cursor": source["id"], "authority": "UNTRUSTED_SOURCES_ONLY"}
		raw, e := codec.Canonical(preview)
		if e != nil {
			return nil, e
		}
		if len(raw) > SummaryBytes-1024 || !fitsSummaryTransport(raw) {
			items = items[:len(items)-1]
			more = true
			break
		}
		next = S(source["id"])
	}
	if !more {
		next = ""
	}
	return Map{"candidate_id": id, "episode_id": p["run_id"], "sources": items, "more": more, "next_cursor": next, "authority": "UNTRUSTED_SOURCES_ONLY", "ordering": "ID_NOT_EVENT_TIME; REFRESH_FOR_NEW_LOWER_IDS"}, nil
}

func ValidSourcePageLimit(v any) bool { return boundedInteger(v, 20) && I(v) > 0 }
