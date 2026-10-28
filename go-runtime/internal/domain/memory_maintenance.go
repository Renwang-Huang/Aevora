package domain

import (
	"context"
	"time"
)

func (r Repo) MemoryCheckGuard(ctx context.Context, candidate, project, basis string, record bool) (Map, error) {
	if !shaPattern.MatchString(basis) {
		return nil, ErrInvalid
	}
	view, e := r.Inspect(ctx, candidate)
	if e != nil {
		return nil, e
	}
	bounds := M(M(M(view["candidate"])["body"])["scope"])
	if !contains(bounds["target_project"], project) {
		return nil, ErrInvalid
	}
	state := S(M(view["head"])["state"])
	id := "memory-check-basis:" + H(candidate)
	prior, e := r.Get(ctx, "AuditEvent", id)
	if e != nil {
		return nil, e
	}
	if state == "WITHDRAWN" || state == "REJECTED" || state == "SUPERSEDED" {
		return Map{"status": "INACTIVE"}, nil
	}
	if prior != nil && prior["basis"] != basis {
		next := "REJECTED"
		if state == "PUBLISHED" || state == "ADMITTED_BOUNDED" || state == "PUBLISHING" {
			next = "WITHDRAWN"
		}
		_, e = r.Transition(ctx, candidate, next, S(view["head_sha256"]), "check-input-changed-"+basis[:24], "The artifact or fixed verification policy supporting this candidate changed", ReviewGrant{Principal: "memory-check-maintenance", ExpiresAt: time.Now().Add(5 * time.Minute).UTC().Format(time.RFC3339Nano)}, Map{})
		return Map{"status": "INPUT_CHANGED_WITHDRAWN", "historical_queries": "PRESERVED"}, e
	}
	if prior != nil {
		return Map{"status": "UNCHANGED_VERIFIED"}, nil
	}
	if record {
		if state != "PUBLISHED" && state != "ADMITTED_BOUNDED" {
			return nil, ErrInvalid
		}
		if e = r.Put(ctx, "AuditEvent", Map{"id": id, "event": "MEMORY_CHECK_BASIS", "candidate_id": candidate, "project": project, "basis": basis, "created_at": Now()}); e != nil {
			return nil, e
		}
		return Map{"status": "BASIS_RECORDED"}, nil
	}
	return Map{"status": "CHECK_REQUIRED"}, nil
}

func (r Repo) MemoryCheckProbe(ctx context.Context, candidate, project, basis string) (Map, error) {
	if !shaPattern.MatchString(basis) {
		return nil, ErrInvalid
	}
	view, e := r.Inspect(ctx, candidate)
	if e != nil {
		return nil, e
	}
	if !contains(M(M(M(view["candidate"])["body"])["scope"])["target_project"], project) {
		return nil, ErrInvalid
	}
	state := S(M(view["head"])["state"])
	if state == "REJECTED" || state == "WITHDRAWN" || state == "SUPERSEDED" {
		return Map{"status": "INACTIVE", "candidate_id": candidate}, nil
	}
	prior, e := r.Get(ctx, "AuditEvent", "memory-check-basis:"+H(candidate))
	if e != nil {
		return nil, e
	}
	if prior == nil {
		return Map{"status": "CHECK_REQUIRED", "candidate_id": candidate}, nil
	}
	if prior["basis"] == basis {
		return Map{"status": "UNCHANGED_VERIFIED", "candidate_id": candidate}, nil
	}
	return Map{"status": "MUTATION_REQUIRED", "candidate_id": candidate}, nil
}

func (r Repo) MemoryCheckUnavailable(ctx context.Context, candidate, project string, mutate bool) (Map, error) {
	return r.memoryCheckUnavailable(ctx, candidate, project, mutate, 0)
}
func (r Repo) memoryCheckUnavailable(ctx context.Context, candidate, project string, mutate bool, depth int) (Map, error) {
	if depth >= 16 {
		return nil, ErrConflict
	}
	view, e := r.Inspect(ctx, candidate)
	if e != nil {
		return nil, e
	}
	if !contains(M(M(M(view["candidate"])["body"])["scope"])["target_project"], project) {
		return nil, ErrInvalid
	}
	prior, e := r.Get(ctx, "AuditEvent", "memory-check-basis:"+H(candidate))
	if e != nil {
		return nil, e
	}
	state := S(M(view["head"])["state"])
	if prior == nil {
		links, e := r.Edges(ctx, "Candidate", candidate, "DERIVED_FROM", true)
		if e != nil {
			return nil, e
		}
		affected := 0
		for _, link := range links {
			if link.SourceLabel != "Candidate" {
				continue
			}
			v, e := r.memoryCheckUnavailable(ctx, link.SourceID, project, mutate, depth+1)
			if e != nil {
				return nil, e
			}
			if v["status"] == "MUTATION_REQUIRED" && !mutate {
				return v, nil
			}
			if v["status"] == "CHECK_UNAVAILABLE_WITHDRAWN" {
				affected++
			}
		}
		return Map{"status": "ORIGINAL_OBSERVATION_RETAINED", "affected_projections": affected, "candidate_id": candidate}, nil
	}
	if state == "WITHDRAWN" || state == "REJECTED" || state == "SUPERSEDED" {
		return Map{"status": "INACTIVE", "candidate_id": candidate}, nil
	}
	if !mutate {
		return Map{"status": "MUTATION_REQUIRED"}, nil
	}
	next := "WITHDRAWN"
	if state == "PROPOSED" || state == "EVIDENCE_PENDING" {
		next = "REJECTED"
	}
	_, e = r.Transition(ctx, candidate, next, S(view["head_sha256"]), "check-input-unavailable", "The independent check inputs or protected owner plan are unavailable", ReviewGrant{Principal: "memory-check-maintenance", ExpiresAt: time.Now().Add(5 * time.Minute).UTC().Format(time.RFC3339Nano)}, Map{})
	return Map{"status": "CHECK_UNAVAILABLE_WITHDRAWN", "candidate_id": candidate}, e
}

func (r Repo) TaskSourceRevoked(ctx context.Context, id string) (bool, error) {
	p, e := r.Get(ctx, "AuditEvent", "memory-source-revoked:"+H(id))
	return p != nil, e
}
func (r Repo) CheckTaskDependencies(ctx context.Context, candidate string) error {
	links, e := r.Edges(ctx, "Candidate", candidate, "DERIVED_FROM", false)
	if e != nil {
		return e
	}
	for _, link := range links {
		if link.TargetLabel != "ExternalObservation" {
			continue
		}
		p, e := r.Required(ctx, "ExternalObservation", link.TargetID)
		if e != nil {
			return e
		}
		if p["record_kind"] != TaskEventKind {
			continue
		}
		revoked, e := r.TaskSourceRevoked(ctx, link.TargetID)
		if e != nil {
			return e
		}
		if revoked {
			return ErrConflict
		}
	}
	return nil
}
func (r Repo) RevokeTaskSource(ctx context.Context, id, project string) (Map, error) {
	source, e := r.Required(ctx, "ExternalObservation", id)
	if e != nil || source["record_kind"] != TaskEventKind || M(source["event"])["project"] != project {
		return nil, ErrInvalid
	}
	if ValidateRecord("ExternalObservation", source) != nil {
		return nil, ErrConflict
	}
	auditID := "memory-source-revoked:" + H(id)
	old, e := r.Get(ctx, "AuditEvent", auditID)
	if e != nil {
		return nil, e
	}
	if old != nil {
		return Map{"status": "SOURCE_REVOKED", "idempotent_replay": true}, nil
	}
	links, e := r.Edges(ctx, "ExternalObservation", id, "DERIVED_FROM", true)
	if e != nil {
		return nil, e
	}
	affected := []any{}
	for _, link := range links {
		if link.SourceLabel != "Candidate" {
			continue
		}
		view, e := r.Inspect(ctx, link.SourceID)
		if e != nil {
			return nil, e
		}
		state := S(M(view["head"])["state"])
		next := ""
		if state == "PUBLISHED" || state == "ADMITTED_BOUNDED" || state == "PUBLISHING" {
			next = "WITHDRAWN"
		} else if state == "PROPOSED" || state == "EVIDENCE_PENDING" {
			next = "REJECTED"
		}
		if next != "" {
			_, e = r.Transition(ctx, link.SourceID, next, S(view["head_sha256"]), "source-revoke-"+H(id)[:24], "A structured source dependency was revoked by its trusted project owner", ReviewGrant{Principal: "memory-source-maintenance", ExpiresAt: time.Now().Add(5 * time.Minute).UTC().Format(time.RFC3339Nano)}, Map{})
			if e != nil {
				return nil, e
			}
			affected = append(affected, link.SourceID)
		}
	}
	if e = r.Put(ctx, "AuditEvent", Map{"id": auditID, "event": "TASK_SOURCE_REVOKED", "source_id": id, "project": project, "created_at": Now(), "affected_candidates": affected}); e != nil {
		return nil, e
	}
	return Map{"status": "SOURCE_REVOKED", "affected_candidates": affected, "historical_queries": "PRESERVED"}, nil
}
