package domain

import (
	"context"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"regexp"
)

var usageKey = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`)

// RecordObservationUse appends a caller's report, never an adoption proof or
// an engineering outcome. Candidate existence is checked; exposure is not.
// A stable key lets a caller explicitly reconcile an uncertain response.
func (s Service) RecordObservationUse(ctx context.Context, input Map) (Map, error) {
	if !subset(input, "candidate_id report_key purpose disposition reason elapsed_seconds") ||
		!has(input, "candidate_id") || !has(input, "report_key") || !has(input, "purpose") ||
		!has(input, "disposition") || !has(input, "reason") || !usageKey.MatchString(S(input["report_key"])) ||
		!stringSet("DEBUGGING PLANNING IMPLEMENTATION VALIDATION OTHER")[S(input["purpose"])] ||
		!stringSet("INVESTIGATED REUSED REJECTED NOT_RELEVANT INCONCLUSIVE")[S(input["disposition"])] ||
		!publicText(input["reason"], 800) {
		return nil, ErrInvalid
	}
	if has(input, "elapsed_seconds") && !boundedInteger(input["elapsed_seconds"], 86400) {
		return nil, ErrInvalid
	}
	candidateID := S(input["candidate_id"])
	if !storage.ValidID(candidateID) {
		return nil, ErrInvalid
	}
	candidate, err := s.Repo.Required(ctx, "Candidate", candidateID)
	if err != nil {
		return nil, ErrInvalid
	}
	claim := Clone(input)
	claim["run_id"], claim["candidate_body_sha256"] = s.Run, candidate["body_sha256"]
	id := "external-observation:usage:" + H([]any{s.Run, input["report_key"]})
	old, err := s.Repo.Get(ctx, "ExternalObservation", id)
	if err != nil {
		return nil, err
	}
	created := s.now()
	if old != nil {
		created = S(old["created_at"])
	}
	duration := "time not reported"
	if has(input, "elapsed_seconds") {
		duration = fmt.Sprintf("reported %v s", input["elapsed_seconds"])
	}
	p := Map{
		"id": id, "run_id": s.Run, "record_kind": "OBSERVATION_USE_CLAIM", "candidate_id": candidateID,
		"candidate_body_sha256": candidate["body_sha256"], "source_sha256": H(claim),
		"status": "UNTRUSTED_USAGE_CLAIM", "authority": "EXTERNAL_UNVERIFIED", "trusted_outcome": "NOT_CREATED",
		"attribution": "UNKNOWN", "created_at": created, "purpose": input["purpose"], "disposition": input["disposition"],
		"elapsed_seconds": defaultValue(input, "elapsed_seconds", nil),
		"public_summary":  fmt.Sprintf("Agent-reported observation use (%s; %s; %s): %s", input["purpose"], input["disposition"], duration, input["reason"]),
	}
	if err = s.Repo.Put(ctx, "ExternalObservation", p); err != nil {
		return nil, err
	}
	if err = s.Repo.PutEdge(ctx, "DERIVED_FROM", "ExternalObservation", id, "Candidate", candidateID, nil); err != nil {
		return nil, err
	}
	return Map{"status": "RECORDED_UNTRUSTED", "report_id": id, "candidate_id": candidateID, "run_id": s.Run,
		"candidate_existence": "CHECKED", "exposure": "NOT_VERIFIED", "adoption": "CLAIM_ONLY",
		"trusted_outcome": "NOT_CREATED", "causal_benefit": "UNKNOWN", "idempotent_replay": old != nil}, nil
}
