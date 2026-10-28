package domain

import (
	"context"
	"strings"
)

// JSONCheckProjection never promotes arbitrary reported repair narratives.
// Only the fixed verifier recipe and its actual required check identities enter
// the bounded publication; original observations remain untrusted history.
func (r Repo) JSONCheckProjection(ctx context.Context, args Map, create bool) (Map, error) {
	if !exact(args, "candidate_id project suite_sha256 evaluator_sha256 source_policy_sha256 automation_policy_sha256 required_tests") {
		return nil, ErrInvalid
	}
	for _, k := range []string{"suite_sha256", "evaluator_sha256", "source_policy_sha256", "automation_policy_sha256"} {
		if !shaPattern.MatchString(S(args[k])) {
			return nil, ErrInvalid
		}
	}
	original, e := r.Required(ctx, "Candidate", S(args["candidate_id"]))
	if e != nil {
		return nil, e
	}
	project := S(args["project"])
	if !contains(M(M(original["body"])["scope"])["target_project"], project) {
		return nil, ErrInvalid
	}
	tests := A(args["required_tests"])
	if len(tests) < 1 || len(tests) > 100 {
		return nil, ErrInvalid
	}
	names := []string{}
	for _, v := range tests {
		if !publicText(v, 160) || !strings.HasPrefix(S(v), "json_contract::") {
			return nil, ErrInvalid
		}
		if len(names) < 12 {
			names = append(names, S(v))
		}
	}
	key := "json-contract-" + H(args)[:24]
	id := "candidate:" + S(original["run_id"]) + ":" + key
	prior, e := r.Get(ctx, "Candidate", id)
	if e != nil {
		return nil, e
	}
	links, e := r.Edges(ctx, "Candidate", S(original["id"]), "DERIVED_FROM", true)
	if e != nil {
		return nil, e
	}
	for _, link := range links {
		if link.SourceLabel != "Candidate" || link.SourceID == id {
			continue
		}
		child, e := r.Required(ctx, "Candidate", link.SourceID)
		if e != nil {
			return nil, e
		}
		if !strings.HasPrefix(S(M(child["body"])["candidate_key"]), "json-contract-") || M(child["body"])["derived_from_candidate_id"] != original["id"] {
			continue
		}
		state, e := r.MemoryCheckUnavailable(ctx, link.SourceID, project, create)
		if e != nil {
			return nil, e
		}
		if !create && state["status"] == "MUTATION_REQUIRED" {
			return Map{"status": "MUTATION_REQUIRED"}, nil
		}
	}
	if prior != nil {
		return r.Inspect(ctx, id)
	}
	if !create {
		return Map{"status": "MUTATION_REQUIRED"}, nil
	}
	bounds := Map{"target_project": []any{project}, "operation_semantics": []any{"json_artifact_contract_only"}}
	body := Map{"candidate_key": key, "derived_from_candidate_id": original["id"], "title": "Pinned JSON artifact contract: " + project, "strategy": "Run the independently pinned JSON artifact checks before relying on this artifact's structure. Required checks: " + strings.Join(names, ", ") + ". Treat reported repair steps as untrusted investigative leads.", "public_summary": "The independent checker establishes only fixed JSON artifact predicates. It does not verify the original repair narrative, runtime behavior, adoption or causal benefit.", "necessary_conditions": bounds, "scope": Clone(bounds), "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{"Only the independently pinned JSON artifact contract is supported.", "Original engineering observations remain untrusted; no repair claim is promoted by this projection."}, "source_references": []any{}}
	result, e := r.Propose(ctx, S(original["run_id"]), body)
	if e != nil {
		return nil, e
	}
	id = S(result["candidate_id"])
	if e = r.PutEdge(ctx, "DERIVED_FROM", "Candidate", id, "Candidate", S(original["id"]), nil); e != nil {
		return nil, e
	}
	links, e = r.Edges(ctx, "Candidate", S(original["id"]), "DERIVED_FROM", false)
	if e != nil {
		return nil, e
	}
	for _, link := range links {
		if link.TargetLabel == "ExternalObservation" {
			if e = r.PutEdge(ctx, "DERIVED_FROM", "Candidate", id, "ExternalObservation", link.TargetID, nil); e != nil {
				return nil, e
			}
		}
	}
	return r.Inspect(ctx, id)
}
