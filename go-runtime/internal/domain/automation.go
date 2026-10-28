package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"time"
)

const AutomationPolicyVersion = "aevora.automation-policy/1"

// The protected policy is a standing delegation to a trusted verification job,
// not a grant to the candidate or an arbitrary model-generated test result.
func ValidateAutomationPolicy(p Map) error {
	if !exact(p, "schema_version policy_id backend_id source_policy_sha256 scope target_state") || p["schema_version"] != AutomationPolicyVersion || !validLocal(S(p["policy_id"]), 64) || !shaPattern.MatchString(S(p["backend_id"])) || !shaPattern.MatchString(S(p["source_policy_sha256"])) || !stringSet("ADMITTED_BOUNDED PUBLISHED")[S(p["target_state"])] {
		return ErrInvalid
	}
	if err := ValidateScope(p["scope"]); err != nil || len(M(p["scope"])) == 0 {
		return ErrInvalid
	}
	for _, values := range M(p["scope"]) {
		for _, value := range A(values) {
			if text, ok := value.(string); ok && sensitive.MatchString(text) {
				return ErrInvalid
			}
		}
	}
	return nil
}

func LoadAutomationPolicy(path string) (Map, error) {
	raw, err := platform.ReadPrivate(path, 65536)
	if err != nil {
		return nil, err
	}
	value, err := codec.Parse(raw)
	if err != nil || ValidateAutomationPolicy(M(value)) != nil {
		return nil, ErrInvalid
	}
	return M(value), nil
}

func automationScope(candidate, bounds Map) (Map, error) {
	result := Clone(candidate)
	for key, allowed := range bounds {
		if old, exists := result[key]; exists {
			narrowed := []any{}
			for _, value := range A(old) {
				if contains(allowed, value) {
					narrowed = append(narrowed, value)
				}
			}
			if len(narrowed) == 0 {
				return nil, ErrInvalid
			}
			result[key] = narrowed
		} else {
			result[key] = allowed
		}
	}
	return result, nil
}

// AutomateCandidate must run in the Host's existing write transaction. Source
// verification, lifecycle transitions and the operation receipt commit together.
func (r Repo) AutomateCandidate(ctx context.Context, backend, id, expected string, policy, sourcePolicy Map, root, pin string) (Map, error) {
	if ValidateAutomationPolicy(policy) != nil || policy["backend_id"] != backend || ValidatePolicy(sourcePolicy) != nil || policy["source_policy_sha256"] != H(sourcePolicy) || !shaPattern.MatchString(expected) || !shaPattern.MatchString(pin) {
		return nil, ErrInvalid
	}
	if err := r.CheckTaskDependencies(ctx, id); err != nil {
		return nil, err
	}
	view, err := r.Inspect(ctx, id)
	if err != nil {
		return nil, err
	}
	candidate, state := M(view["candidate"]), S(M(view["head"])["state"])
	body := M(candidate["body"])
	if state != "PROPOSED" && state != "EVIDENCE_PENDING" && state != "ADMITTED_BOUNDED" && state != S(policy["target_state"]) {
		return nil, ErrConflict
	}
	if state != S(policy["target_state"]) && view["head_sha256"] != expected {
		return nil, ErrConflict
	}
	if len(M(body["necessary_conditions"])) == 0 || len(M(body["scope"])) == 0 {
		return Map{"status": "KEPT_AS_OBSERVATION", "candidate_id": id, "reason": "BOUNDS_NOT_ESTABLISHED", "publication": "NOT_PUBLISHED"}, nil
	}
	scope, err := automationScope(M(body["scope"]), M(policy["scope"]))
	if err != nil {
		return nil, err
	}
	verified, err := r.VerifyProjectCandidate(ctx, id, sourcePolicy, root, pin)
	if err != nil {
		return nil, err
	}
	if verified["outcome_verdict"] != "PASS" {
		return Map{"status": "NOT_PROMOTED", "candidate_id": id, "reason": "VERIFIER_NON_PASS", "source": verified["source"], "publication": "NOT_PUBLISHED"}, nil
	}
	sourceID := S(M(verified["source"])["id"])
	metadata := Map{"source_id": sourceID, "scope": scope, "strength": "BOUNDED_SUPPORT_NOT_CAUSAL"}
	if _, err = r.Admission(ctx, candidate, metadata); err != nil {
		return nil, err
	}
	action := H(Map{"candidate": id, "head": expected, "policy": H(policy), "receipt": pin})
	prefix := "auto-" + action[:32]
	principal := "automation:" + S(policy["policy_id"]) + ":" + H(policy)[:16]
	result := Map{"status": policy["target_state"], "candidate_id": id, "policy_id": policy["policy_id"], "policy_sha256": H(policy), "source_id": sourceID, "reviewed_scope": scope, "adoption": "UNKNOWN", "causal_benefit": "UNKNOWN"}
	if state == S(policy["target_state"]) {
		// Reconciliation accepts only this exact completed automation, never a
		// different policy's promotion or a withdrawn/superseded publication.
		key := prefix + "-admit"
		if state == "PUBLISHED" {
			key = prefix + "-publish-complete"
		}
		event, err := r.Get(ctx, "CandidateEvent", "candidate-event:"+H(id)+":"+key)
		if err != nil || event == nil || event["principal"] != principal || (state == "ADMITTED_BOUNDED" && !codec.Equal(event["metadata"], metadata)) {
			return nil, ErrConflict
		}
		if state == "PUBLISHED" {
			eid := "experience:published:" + H(id)
			allowed, err := r.PublicationAllowed(ctx, id, eid)
			if err != nil || !allowed {
				return nil, ErrConflict
			}
			result["experience_id"] = eid
		}
		result["idempotent_replay"] = true
		return result, nil
	}
	grant := ReviewGrant{Principal: principal, ExpiresAt: time.Now().Add(10 * time.Minute).UTC().Format(time.RFC3339Nano)}
	reason := "Standing policy " + S(policy["policy_id"]) + " sha256 " + H(policy)
	if state == "PROPOSED" {
		if _, err = r.Transition(ctx, id, "EVIDENCE_PENDING", S(view["head_sha256"]), prefix+"-pending", reason, grant, Map{}); err != nil {
			return nil, err
		}
		view, err = r.Inspect(ctx, id)
		if err != nil {
			return nil, err
		}
	}
	if state == "ADMITTED_BOUNDED" {
		// A separately authorized publish job may continue an admitted item only
		// with exactly the same verified source and reviewed bounds.
		for _, raw := range A(view["events"]) {
			event := M(raw)
			if event["to_state"] == "ADMITTED_BOUNDED" && !codec.Equal(event["metadata"], metadata) {
				return nil, ErrConflict
			}
		}
	} else {
		if _, err = r.Transition(ctx, id, "ADMITTED_BOUNDED", S(view["head_sha256"]), prefix+"-admit", reason, grant, metadata); err != nil {
			return nil, err
		}
	}
	if policy["target_state"] == "PUBLISHED" {
		view, err = r.Inspect(ctx, id)
		if err != nil {
			return nil, err
		}
		published, err := r.Publish(ctx, id, S(view["head_sha256"]), prefix+"-publish", reason, grant)
		if err != nil {
			return nil, err
		}
		result["experience_id"] = published["experience_id"]
	}
	return result, nil
}
