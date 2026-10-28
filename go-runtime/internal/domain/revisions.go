package domain

import (
	"context"
)

func (r Repo) AppendGovernance(ctx context.Context, p Map) (Map, error) {
	id := S(p["id"])
	auditID := "governance-complete:" + H(id)
	record := Clone(p)
	record["completion_audit_id"], record["authority"] = auditID, "TRUSTED_HOST_GOVERNANCE"
	if !has(record, "created_at") {
		record["created_at"] = record["effective_at"]
	}
	if !has(record, "scope") {
		record["scope"] = Map{}
	}
	if !has(record, "material_fact_keys") {
		record["material_fact_keys"] = []any{}
	}
	if e := ValidateRecord("GovernanceEvent", record); e != nil {
		return nil, e
	}
	if _, e := r.Required(ctx, S(record["target_label"]), S(record["target_id"])); e != nil {
		return nil, e
	}
	if e := r.Put(ctx, "GovernanceEvent", record); e != nil {
		return nil, e
	}
	if e := r.PutEdge(ctx, "GOVERNS", "GovernanceEvent", id, S(record["target_label"]), S(record["target_id"]), nil); e != nil {
		return nil, e
	}
	if e := r.Put(ctx, "AuditEvent", Map{"id": auditID, "event": "governance_event_complete", "governance_event_id": id, "record_sha256": H(record)}); e != nil {
		return nil, e
	}
	return Map{"status": "APPENDED", "event_id": id, "completion_audit_id": auditID}, nil
}
func (r Repo) AppendRule(ctx context.Context, eid string, rule, revision Map) (Map, error) {
	if _, e := r.Required(ctx, "Experience", eid); e != nil {
		return nil, e
	}
	premises := A(rule["premises"])
	if len(premises) == 0 {
		return nil, ErrInvalid
	}
	ids := map[string]bool{}
	for _, v := range premises {
		p := M(v)
		if e := ValidateRecord("Premise", p); e != nil {
			return nil, e
		}
		if !facts[S(p["fact_key"])] || ids[S(p["id"])] {
			return nil, ErrInvalid
		}
		ids[S(p["id"])] = true
	}
	record := Clone(rule)
	delete(record, "premises")
	record["premise_ids"], record["premise_count"] = sortedSet(ids), len(ids)
	if e := ValidateRecord("Rule", record); e != nil {
		return nil, e
	}
	rid := S(revision["id"])
	auditID := "publication:" + H(rid)
	rev := Clone(revision)
	rev["experience_id"], rev["revision_kind"], rev["declared_rule_id"], rev["publication_audit_id"], rev["attribution"] = eid, "rule_publication", record["id"], auditID, "UNKNOWN"
	if !has(rev, "scope") {
		rev["scope"] = Map{}
	}
	if !has(rev, "valid_until") {
		rev["valid_until"] = nil
	}
	rev["created_at"] = rev["valid_from"]
	if e := ValidateRecord("ExperienceRevision", rev); e != nil {
		return nil, e
	}
	for _, v := range A(rev["supersedes_ids"]) {
		id := S(v)
		if id == rid {
			return nil, ErrInvalid
		}
		old, e := r.Required(ctx, "ExperienceRevision", id)
		if e != nil || old["experience_id"] != eid {
			return nil, ErrInvalid
		}
	}
	if e := r.Put(ctx, "ExperienceRevision", rev); e != nil {
		return nil, e
	}
	if e := r.Put(ctx, "Rule", record); e != nil {
		return nil, e
	}
	if e := r.PutEdge(ctx, "HAS_REVISION", "Experience", eid, "ExperienceRevision", rid, nil); e != nil {
		return nil, e
	}
	if e := r.PutEdge(ctx, "USES_RULE", "ExperienceRevision", rid, "Rule", S(record["id"]), nil); e != nil {
		return nil, e
	}
	for _, v := range premises {
		p := M(v)
		if e := r.Put(ctx, "Premise", p); e != nil {
			return nil, e
		}
		if e := r.PutEdge(ctx, "REQUIRES", "Rule", S(record["id"]), "Premise", S(p["id"]), nil); e != nil {
			return nil, e
		}
	}
	for _, v := range A(rev["supersedes_ids"]) {
		if e := r.PutEdge(ctx, "SUPERSEDES", "ExperienceRevision", rid, "ExperienceRevision", S(v), nil); e != nil {
			return nil, e
		}
	}
	if e := r.Put(ctx, "AuditEvent", Map{"id": auditID, "event": "rule_publication_complete", "revision_id": rid, "revision_sha256": H(rev)}); e != nil {
		return nil, e
	}
	return Map{"status": "PUBLISHED", "revision_id": rid, "rule_id": record["id"], "completion_audit_id": auditID}, nil
}

// Observation payloads stay in their own append-only authority class.
func (r Repo) ExternalObservation(ctx context.Context, run, pin, summary string) (Map, error) {
	if !shaPattern.MatchString(pin) || !storageID(run) || !publicText(summary, 4000) {
		return nil, ErrInvalid
	}
	p := Map{"id": "external-observation:" + H([]any{run, pin, summary}), "run_id": run, "source_sha256": pin, "public_summary": summary, "authority": "EXTERNAL_UNVERIFIED", "trusted_outcome": "NOT_CREATED", "attribution": "UNKNOWN"}
	if e := r.Put(ctx, "ExternalObservation", p); e != nil {
		return nil, e
	}
	return p, nil
}
