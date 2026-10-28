package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"sort"
)

// FeedbackSource consumes only a source already minted by the Host verifier.
// Public decisions and arbitrary caller-supplied verdicts cannot enter here.
func (r Repo) FeedbackSource(ctx context.Context, sourceID string) (Map, error) {
	source, e := r.Required(ctx, "SourceVerification", sourceID)
	if e != nil {
		return nil, e
	}
	if id := S(source["candidate_id"]); id != "" {
		candidate, e := r.Required(ctx, "Candidate", id)
		if e != nil || source["run_id"] != candidate["run_id"] {
			return nil, ErrInvalid
		}
		if e = r.RequireEdge(ctx, "HAS_SOURCE_VERIFICATION", "Candidate", id, "SourceVerification", sourceID); e != nil {
			return nil, e
		}
	} else {
		if source["verification_scope"] != "OUTCOME_ONLY" || !shaPattern.MatchString(S(source["authorized_plan_sha256"])) {
			return nil, ErrInvalid
		}
		audit, e := r.Required(ctx, "AuditEvent", "source-authorization:"+H(sourceID))
		if e != nil || audit["event"] != "authorized_evaluator_source_complete" || audit["source_id"] != sourceID || audit["plan_sha256"] != source["authorized_plan_sha256"] || audit["verification_scope"] != "OUTCOME_ONLY" {
			return nil, ErrInvalid
		}
		if e = r.RequireEdge(ctx, "VERIFIES", "SourceVerification", sourceID, "VerifiedOutcome", S(source["outcome_id"])); e != nil {
			return nil, e
		}
	}
	outcome, e := r.Required(ctx, "VerifiedOutcome", S(source["outcome_id"]))
	if e != nil || outcome["run_id"] != source["run_id"] {
		return nil, ErrInvalid
	}
	contexts, e := r.targets(ctx, "VerifiedOutcome", S(outcome["id"]), "IN_CONTEXT", "Context")
	if e != nil || len(contexts) != 1 || !codec.Equal(contexts[0]["facts"], source["facts"]) {
		return nil, ErrConflict
	}
	context := contexts[0]
	tasks, e := r.targets(ctx, "Context", S(context["id"]), "FOR_TASK", "Task")
	if e != nil || len(tasks) != 1 {
		return nil, ErrConflict
	}
	task := tasks[0]
	run := S(outcome["run_id"])
	rows, e := r.List(ctx, "Query", storage.Filter{Run: run, Limit: 4097})
	if e != nil {
		return nil, e
	}
	if len(rows) > 4096 {
		return nil, ErrInvalid
	}
	queries := map[string][]Map{}
	for _, q := range rows {
		edges, e := r.Edges(ctx, "Query", S(q["id"]), "CONSIDERED", false)
		if e != nil {
			return nil, e
		}
		for _, edge := range edges {
			if edge.TargetLabel != "Experience" {
				continue
			}
			if q["authority"] != "scoped_broker_run" || !contains(q["candidate_experience_ids"], edge.TargetID) {
				return nil, ErrConflict
			}
			if e = r.RequireEdge(ctx, "CONSIDERED", "Query", S(q["id"]), "Experience", edge.TargetID); e != nil {
				return nil, e
			}
			queries[edge.TargetID] = append(queries[edge.TargetID], q)
		}
	}
	decisionRows, e := r.List(ctx, "Decision", storage.Filter{Run: run, Limit: 4097})
	if e != nil || len(decisionRows) > 4096 {
		return nil, ErrInvalid
	}
	decisions := map[string][]Map{}
	for _, d := range decisionRows {
		eid, qid := S(d["experience_id"]), S(d["query_id"])
		var query Map
		for _, q := range queries[eid] {
			if q["id"] == qid {
				query = q
			}
		}
		if query == nil || d["authority"] != "UNTRUSTED_PARTICIPANT_CLAIM" || d["adoption"] != "CLAIM_ONLY" || d["attribution"] != "UNKNOWN" {
			return nil, ErrConflict
		}
		for _, edge := range [][5]string{{"DECIDED", "Decision", S(d["id"]), "Experience", eid}, {"RESPONDS_TO", "Decision", S(d["id"]), "Query", qid}} {
			if e = r.RequireEdge(ctx, edge[0], edge[1], edge[2], edge[3], edge[4]); e != nil {
				return nil, e
			}
		}
		sid := M(query["query_snapshot_ids"])[eid]
		if !codec.Equal(d["query_snapshot_id"], sid) {
			return nil, ErrConflict
		}
		if sid != nil {
			if e = r.RequireEdge(ctx, "AT_SNAPSHOT", "Query", qid, "QuerySnapshot", S(sid)); e != nil {
				return nil, e
			}
		}
		decisions[eid] = append(decisions[eid], d)
	}
	selected := []string{}
	for id := range queries {
		selected = append(selected, id)
	}
	sort.Strings(selected)
	feedbackIDs, receipts := []any{}, []any{}
	outcomeDigest := defaultValue(outcome, "immutable_digest", H(outcome))
	created := outcome["evaluated_at"]
	if _, e = timestamp(created); e != nil {
		return nil, e
	}
	completionID := "ingestion:source:" + H(sourceID)
	type plan struct {
		feedback, revision, evidence Map
		rules                        []string
		queries, decisions           []Map
	}
	plans := []plan{}
	for _, eid := range selected {
		if _, e = r.Required(ctx, "Experience", eid); e != nil {
			return nil, e
		}
		baseID := eid + "/revision/initial"
		base, e := r.Required(ctx, "ExperienceRevision", baseID)
		if e != nil || base["experience_id"] != eid {
			return nil, ErrConflict
		}
		if e = r.RequireEdge(ctx, "HAS_REVISION", "Experience", eid, "ExperienceRevision", baseID); e != nil {
			return nil, e
		}
		rules, e := r.targets(ctx, "ExperienceRevision", baseID, "USES_RULE", "Rule")
		if e != nil || len(rules) == 0 {
			return nil, ErrConflict
		}
		ruleIDs, snapshotIDs, revisionIDs := map[string]bool{}, map[string]bool{}, map[string]bool{}
		for _, rule := range rules {
			ruleIDs[S(rule["id"])] = true
		}
		snapshotRules := map[string]bool{}
		for _, q := range queries[eid] {
			sid := S(M(q["query_snapshot_ids"])[eid])
			if sid == "" {
				continue
			}
			if e = r.RequireEdge(ctx, "AT_SNAPSHOT", "Query", S(q["id"]), "QuerySnapshot", sid); e != nil {
				return nil, e
			}
			record, e := r.Required(ctx, "QuerySnapshot", sid)
			if e != nil {
				return nil, e
			}
			content := M(record["content"])
			c := M(content["candidate"])
			if c["experience_id"] != eid || !codec.Equal(content["context"], q["task_context"]) {
				return nil, ErrConflict
			}
			snapshotIDs[sid] = true
			for _, id := range A(c["rule_ids"]) {
				snapshotRules[S(id)] = true
			}
			for _, id := range A(M(c["governance_projection"])["selected_revision_ids"]) {
				revisionIDs[S(id)] = true
			}
		}
		if len(snapshotIDs) > 0 {
			ruleIDs = snapshotRules
		}
		suffix := H([]any{outcome["id"], eid})
		rid := eid + "/revision/observed-" + suffix
		qRefs, dRefs := []any{}, []any{}
		for _, q := range queries[eid] {
			qRefs = append(qRefs, Map{"id": q["id"], "payload_sha256": H(q)})
		}
		for _, d := range decisions[eid] {
			dRefs = append(dRefs, Map{"id": d["id"], "payload_sha256": H(d)})
		}
		feedback := Map{"id": "feedback:" + suffix, "run_id": run, "experience_id": eid, "outcome_id": outcome["id"], "outcome_digest": outcomeDigest, "status": "outcome_observed_no_attribution", "attribution": "UNKNOWN", "adoption": "UNVERIFIED", "strategy_association": "UNVERIFIED", "query_records": qRefs, "untrusted_decision_claims": dRefs, "created_at": created, "revision_id": rid, "authority": "TRUSTED_OUTCOME_OBSERVATION_ONLY"}
		revision := Map{"id": rid, "experience_id": eid, "created_at": created, "revision_reason": "outcome_observed_no_attribution", "attribution": "UNKNOWN", "base_revision_id": baseID, "feedback_id": feedback["id"]}
		if len(snapshotIDs) > 0 {
			revision["revision_kind"], revision["query_snapshot_ids"], revision["base_revision_ids"] = "outcome_observation", sortedSet(snapshotIDs), sortedSet(revisionIDs)
			feedback["query_snapshot_ids"], feedback["rule_ids"], feedback["rule_association"] = sortedSet(snapshotIDs), sortedSet(ruleIDs), "ACTUAL_QUERY_SNAPSHOT_EPOCH"
		}
		evidence := Map{"id": "evidence:observed:" + suffix, "source_type": source["origin"], "source_run_id": run, "created_at": created, "public_summary": "An independently verified engineering outcome was observed in a Run that queried this experience. Exposure and decision claims do not establish adoption or causal benefit.", "attribution": "UNKNOWN", "feedback_id": feedback["id"]}
		plans = append(plans, plan{feedback, revision, evidence, stringsOf(sortedSet(ruleIDs)), queries[eid], decisions[eid]})
		feedbackIDs = append(feedbackIDs, feedback["id"])
	}
	completion := Map{"id": completionID, "run_id": run, "event": "trusted_outcome_ingestion_complete", "outcome_id": outcome["id"], "outcome_digest": outcomeDigest, "experience_ids": values(selected), "feedback_ids": feedbackIDs, "created_at": created}
	old, e := r.Get(ctx, "AuditEvent", completionID)
	if e != nil {
		return nil, e
	}
	if old != nil && !codec.Equal(old, completion) {
		return nil, ErrConflict
	}
	action := Map{"id": "action:source:" + H(outcome["id"]), "run_id": run, "kind": "verified_submission_bytes", "submission_digest": outcome["submission_digest"], "created_at": created, "strategy_association": "UNVERIFIED", "mental_influence": "UNVERIFIED", "authority": "TRUSTED_REPORT_PATCH_AND_CANDIDATE_IDENTITIES"}
	if e = r.Put(ctx, "ObservedAction", action); e != nil {
		return nil, e
	}
	if e = r.PutEdge(ctx, "OBSERVED_ACTION", "VerifiedOutcome", S(outcome["id"]), "ObservedAction", S(action["id"]), nil); e != nil {
		return nil, e
	}
	for _, p := range plans {
		eid := S(p.feedback["experience_id"])
		for _, row := range []struct {
			label string
			value Map
		}{{"Feedback", p.feedback}, {"ExperienceRevision", p.revision}} {
			if e = r.Put(ctx, row.label, row.value); e != nil {
				return nil, e
			}
		}
		for _, edge := range [][5]string{{"HAS_FEEDBACK", "Experience", eid, "Feedback", S(p.feedback["id"])}, {"FROM_OUTCOME", "Feedback", S(p.feedback["id"]), "VerifiedOutcome", S(outcome["id"])}, {"REVISES", "Feedback", S(p.feedback["id"]), "ExperienceRevision", S(p.revision["id"])}, {"HAS_REVISION", "Experience", eid, "ExperienceRevision", S(p.revision["id"])}, {"REVISES", "ExperienceRevision", S(p.revision["id"]), "ExperienceRevision", S(p.revision["base_revision_id"])}} {
			if e = r.PutEdge(ctx, edge[0], edge[1], edge[2], edge[3], edge[4], nil); e != nil {
				return nil, e
			}
		}
		for _, rule := range p.rules {
			if e = r.PutEdge(ctx, "USES_RULE", "ExperienceRevision", S(p.revision["id"]), "Rule", rule, nil); e != nil {
				return nil, e
			}
		}
		if e = r.AttachEvidence(ctx, eid, S(p.revision["id"]), "OBSERVED_OUTCOME", p.evidence, outcome, context, task); e != nil {
			return nil, e
		}
		if e = r.PutEdge(ctx, "OBSERVED_ACTION", "Evidence", S(p.evidence["id"]), "ObservedAction", S(action["id"]), nil); e != nil {
			return nil, e
		}
		for _, q := range p.queries {
			if e = r.PutEdge(ctx, "DERIVED_FROM", "Feedback", S(p.feedback["id"]), "Query", S(q["id"]), nil); e != nil {
				return nil, e
			}
		}
		for _, d := range p.decisions {
			if e = r.PutEdge(ctx, "RESPONDS_TO", "Feedback", S(p.feedback["id"]), "Decision", S(d["id"]), nil); e != nil {
				return nil, e
			}
		}
		receipts = append(receipts, Map{"experience_id": eid, "revision_id": p.revision["id"], "evidence_id": p.evidence["id"], "outcome_id": outcome["id"], "relation": "OBSERVED_OUTCOME", "feedback_id": p.feedback["id"], "attribution": "UNKNOWN"})
	}
	if e = r.Put(ctx, "AuditEvent", completion); e != nil {
		return nil, e
	}
	status := "no_exposure_observed"
	if len(receipts) > 0 {
		status = "outcome_observed_no_attribution"
	}
	return Map{"status": "INGESTED", "outcome_id": outcome["id"], "run_id": run, "verdict": outcome["verdict"], "feedback_status": status, "attribution": "UNKNOWN", "receipts": receipts, "completion_audit_id": completionID, "observed_action_id": action["id"]}, nil
}
