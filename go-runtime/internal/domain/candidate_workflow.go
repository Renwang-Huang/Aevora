package domain

import "context"

// PublicCandidate adds only validated narrative and declared bounds. None of
// these fields inherit the authority of a verified source or published rule.
func PublicCandidate(p Map) (Map, error) {
	body := M(p["body"])
	if err := ValidateProposal(body); err != nil {
		return nil, err
	}
	if p["body_sha256"] != H(body) {
		return nil, ErrConflict
	}
	out := Map{}
	for _, key := range []string{"title", "public_summary", "strategy", "necessary_conditions", "inapplicable_conditions", "scope", "unknown_fields", "limitations", "derived_from_candidate_id"} {
		if value, ok := body[key]; ok {
			out[key] = value
		}
	}
	return out, nil
}

// CandidateChecklist describes recorded prerequisites, not a second admission
// engine. Independent source checks remain in Admission and final publication.
func CandidateChecklist(body Map, state string) Map {
	missing := []any{}
	if len(M(body["necessary_conditions"])) == 0 {
		missing = append(missing, "necessary_conditions")
	}
	if len(M(body["scope"])) == 0 {
		missing = append(missing, "scope")
	}
	unknown := []any{}
	for _, key := range A(body["unknown_fields"]) {
		if has(M(body["necessary_conditions"]), S(key)) || has(M(body["scope"]), S(key)) {
			unknown = append(unknown, key)
		}
	}
	action := "VERIFY_SOURCE"
	if len(missing) > 0 {
		action = "DECLARE_BOUNDS"
	} else if len(unknown) > 0 {
		action = "ESTABLISH_REQUIRED_FACTS"
	} else {
		switch state {
		case "PROPOSED":
			action = "REQUEST_EVIDENCE_REVIEW"
		case "ADMITTED_BOUNDED", "PUBLISHING":
			action = "REVIEW_PUBLICATION"
		case "PUBLISHED":
			action = "QUERY_NEW_TASK"
		case "REJECTED", "WITHDRAWN", "SUPERSEDED":
			action = "RETAIN_HISTORY"
		}
	}
	return Map{"scope_status": map[bool]string{true: "UNSCOPED_DRAFT", false: "DECLARED_UNVERIFIED"}[len(missing) > 0],
		"missing_fields": missing, "unknown_required_facts": unknown, "next_action": action,
		"authority": "UNTRUSTED_DECLARATION", "adoption": "UNKNOWN", "causal_benefit": "UNKNOWN"}
}

func (r Repo) CandidatePlan(ctx context.Context, id string) (Map, error) {
	view, err := r.Inspect(ctx, id)
	if err != nil {
		return nil, err
	}
	candidate := M(view["candidate"])
	public, err := PublicCandidate(candidate)
	if err != nil {
		return nil, err
	}
	state := S(M(view["head"])["state"])
	plan := CandidateChecklist(M(candidate["body"]), state)
	sources, err := r.targets(ctx, "Candidate", id, "HAS_SOURCE_VERIFICATION", "SourceVerification")
	if err != nil {
		return nil, err
	}
	checks := []any{}
	qualified := false
	for _, source := range sources {
		_, err := r.Admission(ctx, candidate, Map{"source_id": source["id"], "scope": M(candidate["body"])["scope"], "strength": "BOUNDED_SUPPORT_NOT_CAUSAL"})
		checks = append(checks, Map{"id": source["id"], "origin": source["origin"], "supports_declared_bounds": err == nil})
		qualified = qualified || err == nil
	}
	plan["verification_status"] = "NO_MATCHING_VERIFIED_SOURCE"
	if qualified {
		plan["verification_status"] = "BOUNDED_SOURCE_SUPPORT"
		if state == "EVIDENCE_PENDING" {
			plan["next_action"] = "REVIEW_ADMISSION"
		}
	}
	plan["source_checks"] = checks
	plan["candidate_id"], plan["state"], plan["head_sha256"] = id, state, view["head_sha256"]
	plan["proposal"] = public
	plan["required_channel"] = "TRUSTED_HOST_MANAGEMENT"
	plan["guide"] = "docs/PROJECT_SOURCES.md"
	return plan, nil
}

func (r Repo) DeriveCandidate(ctx context.Context, id, key string, conditions, scope Map) (Map, error) {
	view, err := r.Inspect(ctx, id)
	if err != nil {
		return nil, err
	}
	if len(conditions) == 0 || len(scope) == 0 {
		return nil, ErrInvalid
	}
	original := M(view["candidate"])
	body := Clone(M(original["body"]))
	body["candidate_key"], body["necessary_conditions"], body["scope"], body["derived_from_candidate_id"] = key, conditions, scope, id
	result, err := r.Propose(ctx, S(original["run_id"]), body)
	if err != nil {
		return nil, err
	}
	result["derived_from_candidate_id"] = id
	result["next_step"] = "Inspect the new candidate plan. Declared bounds remain unverified; source verification and explicit review are required. The original candidate is unchanged."
	return result, nil
}
