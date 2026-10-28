package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
)

// AuthorizeEvaluatorSource accepts a separately authorized private evaluator
// plan. The protected policy pins its exact bytes and verified source epoch.
// Raw OrderFlow/Oracle/native-event validation remains in the Python maintainer
// verifier; this is not a consumer-submitted verdict or a pluggable code loader.
func (r Repo) AuthorizeEvaluatorSource(ctx context.Context, policyFile, root string) (Map, error) {
	raw, e := platform.ReadPrivate(policyFile, 65536)
	if e != nil {
		return nil, ErrInvalid
	}
	value, e := codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	policy := M(value)
	if !exact(policy, "schema_version verifier_id verifier_source_sha256 plan_sha256 source_manifest_sha256 run_id candidate_id candidate_body_sha256 facts origin verification_scope") || policy["schema_version"] != "aevora.evaluator-policy/1" || !shaPattern.MatchString(S(policy["plan_sha256"])) || !shaPattern.MatchString(S(policy["source_manifest_sha256"])) || !shaPattern.MatchString(S(policy["verifier_source_sha256"])) || !text(policy["verifier_id"], 240) || !stringSet("natural_agent_run synthetic_or_test_fixture")[S(policy["origin"])] || !stringSet("OUTCOME_ONLY CANDIDATE_SOURCE")[S(policy["verification_scope"])] {
		return nil, ErrInvalid
	}
	facts := M(policy["facts"])
	if e = NormalizeContext(facts, true); e != nil {
		return nil, e
	}
	files, e := OpenEvidence(root)
	if e != nil {
		return nil, ErrInvalid
	}
	defer files.Close()
	raw, e = files.Read("authorized_source.json", 262144, S(policy["plan_sha256"]))
	if e != nil {
		return nil, ErrInvalid
	}
	value, e = codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	plan := M(value)
	if !exact(plan, "schema_version verifier_id verifier_source_sha256 source_manifest_sha256 verification_scope records native_proof") || plan["schema_version"] != "aevora.evaluator-plan/1" {
		return nil, ErrInvalid
	}
	for _, k := range []string{"verifier_id", "verifier_source_sha256", "source_manifest_sha256", "verification_scope"} {
		if !codec.Equal(plan[k], policy[k]) {
			return nil, ErrInvalid
		}
	}
	records := M(plan["records"])
	if !exact(records, "outcome context task source") {
		return nil, ErrInvalid
	}
	outcome, environment, task, source := M(records["outcome"]), M(records["context"]), M(records["task"]), Clone(M(records["source"]))
	for label, p := range map[string]Map{"VerifiedOutcome": outcome, "Context": environment, "Task": task, "SourceVerification": source} {
		if p == nil {
			return nil, ErrInvalid
		}
		if e = ValidateRecord(label, p); e != nil {
			return nil, e
		}
	}
	run := S(policy["run_id"])
	if run == "" || outcome["run_id"] != run || source["run_id"] != run || source["origin"] != policy["origin"] || source["source_sha256"] != policy["source_manifest_sha256"] || source["outcome_id"] != outcome["id"] || source["submission_sha256"] != outcome["patch_sha256"] || !codec.Equal(environment["facts"], facts) || !codec.Equal(source["facts"], facts) || source["causal_benefit"] != "UNKNOWN" || outcome["attribution"] != "UNKNOWN" {
		return nil, ErrInvalid
	}
	copy := Clone(outcome)
	delete(copy, "immutable_digest")
	if outcome["immutable_digest"] != H(copy) {
		return nil, ErrInvalid
	}
	candidateID := S(policy["candidate_id"])
	scope := S(policy["verification_scope"])
	if scope == "CANDIDATE_SOURCE" {
		if candidateID == "" || !shaPattern.MatchString(S(policy["candidate_body_sha256"])) || source["candidate_id"] != candidateID {
			return nil, ErrInvalid
		}
		view, e := r.Inspect(ctx, candidateID)
		if e != nil {
			return nil, e
		}
		c := M(view["candidate"])
		if c["run_id"] != run || c["body_sha256"] != policy["candidate_body_sha256"] {
			return nil, ErrInvalid
		}
	} else if policy["candidate_id"] != nil || policy["candidate_body_sha256"] != nil || has(source, "candidate_id") {
		return nil, ErrInvalid
	}
	proof := M(plan["native_proof"])
	if policy["origin"] == "natural_agent_run" {
		if proof == nil || proof["thread_id"] != source["native_thread_id"] || S(proof["thread_id"]) == "" || proof["thread_id"] == "UNAVAILABLE" || !shaPattern.MatchString(S(proof["raw_source_sha256"])) || outcome["source_type"] != "current_live" || outcome["verification_profile"] != "current_live" {
			return nil, ErrInvalid
		}
		if scope == "CANDIDATE_SOURCE" && (proof["proposal_body_sha256"] != policy["candidate_body_sha256"] || len(A(proof["proposal_event_references"])) == 0 || len(A(proof["host_operation_ids"])) == 0) {
			return nil, ErrInvalid
		}
	}
	id := "source-verification:evaluator:" + H([]any{run, policy["candidate_id"], policy["source_manifest_sha256"], policy["verifier_source_sha256"]})
	if source["id"] != id {
		return nil, ErrInvalid
	}
	source["authorized_plan_sha256"], source["verification_scope"], source["native_proof_sha256"] = policy["plan_sha256"], scope, H(proof)
	for label, p := range map[string]Map{"VerifiedOutcome": outcome, "Context": environment, "Task": task, "SourceVerification": source} {
		if e = r.Put(ctx, label, p); e != nil {
			return nil, e
		}
	}
	for _, edge := range [][5]string{{"IN_CONTEXT", "VerifiedOutcome", S(outcome["id"]), "Context", S(environment["id"])}, {"FOR_TASK", "Context", S(environment["id"]), "Task", S(task["id"])}, {"VERIFIES", "SourceVerification", id, "VerifiedOutcome", S(outcome["id"])}} {
		if e = r.PutEdge(ctx, edge[0], edge[1], edge[2], edge[3], edge[4], nil); e != nil {
			return nil, e
		}
	}
	if candidateID != "" {
		if e = r.PutEdge(ctx, "HAS_SOURCE_VERIFICATION", "Candidate", candidateID, "SourceVerification", id, nil); e != nil {
			return nil, e
		}
	}
	if e = r.Put(ctx, "AuditEvent", Map{"id": "source-authorization:" + H(id), "event": "authorized_evaluator_source_complete", "run_id": run, "source_id": id, "plan_sha256": policy["plan_sha256"], "verification_scope": scope}); e != nil {
		return nil, e
	}
	return Map{"status": "SOURCE_VERIFIED", "source_id": id, "outcome_id": outcome["id"], "outcome_verdict": outcome["verdict"], "origin": policy["origin"], "verification_scope": scope, "causal_benefit": "UNKNOWN", "assurance": "EXPLICIT_HOST_AUTHORIZATION_OF_INDEPENDENT_PRIVATE_VERIFIER_PLAN"}, nil
}
