package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"strings"
	"time"
)

type ReviewGrant struct {
	Principal string `json:"principal"`
	ExpiresAt string `json:"expires_at"`
}

func (g ReviewGrant) Check() error {
	end, e := timestamp(g.ExpiresAt)
	if e != nil || !storageID(g.Principal) {
		return ErrInvalid
	}
	remaining := time.Until(end)
	if remaining <= 0 || remaining > time.Hour {
		return ErrInvalid
	}
	return nil
}
func validLocal(s string, max int) bool {
	return storageID(s) && len(s) <= max && !strings.ContainsAny(s, ":/")
}
func storageID(s string) bool { return idPatternLocal.MatchString(s) }

func (r Repo) Propose(ctx context.Context, run string, body Map) (Map, error) {
	if !storageID(run) {
		return nil, ErrInvalid
	}
	if e := ValidateProposal(body); e != nil {
		return nil, e
	}
	if parent := S(body["derived_from_candidate_id"]); parent != "" {
		original, err := r.Required(ctx, "Candidate", parent)
		if err != nil || original["run_id"] != run {
			return nil, ErrInvalid
		}
		if parent == "candidate:"+run+":"+S(body["candidate_key"]) {
			return nil, ErrInvalid
		}
	}
	if _, e := r.Required(ctx, "Schema", "aevora.graph/1.2"); e != nil {
		return nil, e
	}
	id := "candidate:" + run + ":" + S(body["candidate_key"])
	if !storageID(id) {
		return nil, ErrInvalid
	}
	for _, v := range A(body["source_references"]) {
		ref := M(v)
		p, e := r.Required(ctx, S(ref["kind"]), S(ref["id"]))
		if e != nil || p["run_id"] != run {
			return nil, ErrInvalid
		}
	}
	old, e := r.Get(ctx, "Candidate", id)
	if e != nil {
		return nil, e
	}
	created := Now()
	if old != nil {
		created = S(old["created_at"])
	}
	p := Map{"id": id, "run_id": run, "body": body, "body_sha256": H(body), "created_at": created, "schema_version": CandidateVersion, "authority": "UNTRUSTED_PROPOSAL", "provenance": "UNVERIFIED_UNTIL_HOST_REVIEW", "agent_thread_id": "UNAVAILABLE"}
	if e = r.Put(ctx, "Candidate", p); e != nil {
		return nil, e
	}
	eventID := "candidate-event:" + H(id) + ":proposed"
	event := Map{"id": eventID, "candidate_id": id, "from_state": nil, "to_state": "PROPOSED", "previous_event_id": nil, "sequence": 0, "created_at": created, "request_sha256": H(p), "reason": "Untrusted run-bound proposal", "authority": "UNTRUSTED_PROPOSAL", "metadata": Map{}}
	if e = r.Put(ctx, "CandidateEvent", event); e != nil {
		return nil, e
	}
	headID := "candidate-head:" + H(id)
	head, e := r.Get(ctx, "LifecycleHead", headID)
	if e != nil {
		return nil, e
	}
	if head == nil {
		if e = r.Put(ctx, "LifecycleHead", Map{"id": headID, "candidate_id": id, "event_id": eventID, "sequence": 0, "state": "PROPOSED"}); e != nil {
			return nil, e
		}
	}
	if e = r.PutEdge(ctx, "HAS_LIFECYCLE", "Candidate", id, "LifecycleHead", headID, nil); e != nil {
		return nil, e
	}
	if e = r.PutEdge(ctx, "HAS_CANDIDATE_EVENT", "Candidate", id, "CandidateEvent", eventID, nil); e != nil {
		return nil, e
	}
	scopeStatus, nextStep := "DECLARED_UNVERIFIED", "Host must independently verify the declared bounds and source before admission."
	if len(M(body["necessary_conditions"])) == 0 || len(M(body["scope"])) == 0 {
		scopeStatus = "UNSCOPED_DRAFT"
		nextStep = "Retain this draft. Once conditions and scope are established, submit a new bounded proposal with a new candidate_key. This draft cannot be admitted or published."
	}
	return Map{"status": "PROPOSED_UNTRUSTED", "candidate_id": id, "body_sha256": H(body), "run_id": run, "publication": "NOT_PUBLISHED", "source_type": "UNVERIFIED", "schema_version": CandidateVersion, "scope_status": scopeStatus, "next_step": nextStep}, nil
}
func (r Repo) Inspect(ctx context.Context, id string) (Map, error) {
	candidate, e := r.Required(ctx, "Candidate", id)
	if e != nil {
		return nil, e
	}
	headID := "candidate-head:" + H(id)
	head, e := r.Required(ctx, "LifecycleHead", headID)
	if e != nil {
		return nil, e
	}
	if e = r.RequireEdge(ctx, "HAS_LIFECYCLE", "Candidate", id, "LifecycleHead", headID); e != nil {
		return nil, e
	}
	current := S(head["event_id"])
	expected := I(head["sequence"])
	chain := []any{}
	for current != "" {
		if len(chain) >= 128 {
			return nil, ErrConflict
		}
		event, e := r.Required(ctx, "CandidateEvent", current)
		if e != nil {
			return nil, e
		}
		if event["candidate_id"] != id || I(event["sequence"]) != expected {
			return nil, ErrConflict
		}
		if e = r.RequireEdge(ctx, "HAS_CANDIDATE_EVENT", "Candidate", id, "CandidateEvent", current); e != nil {
			return nil, e
		}
		previous := S(event["previous_event_id"])
		if previous != "" {
			if e = r.RequireEdge(ctx, "PREVIOUS_EVENT", "CandidateEvent", current, "CandidateEvent", previous); e != nil {
				return nil, e
			}
		} else if expected != 0 || event["to_state"] != "PROPOSED" {
			return nil, ErrConflict
		}
		chain = append(chain, event)
		current = previous
		expected--
	}
	if expected != -1 || len(chain) == 0 || M(chain[0])["to_state"] != head["state"] {
		return nil, ErrConflict
	}
	for i := 0; i+1 < len(chain); i++ {
		newer, older := M(chain[i]), M(chain[i+1])
		if newer["from_state"] != older["to_state"] || !transitions[S(older["to_state"])][S(newer["to_state"])] {
			return nil, ErrConflict
		}
	}
	fresh, e := r.FreshHead(ctx, headID)
	if e != nil {
		return nil, e
	}
	if !codec.Equal(fresh, head) {
		return nil, ErrConflict
	}
	for i, j := 0, len(chain)-1; i < j; i, j = i+1, j-1 {
		chain[i], chain[j] = chain[j], chain[i]
	}
	return Map{"candidate": candidate, "head": head, "head_sha256": H(head), "events": chain, "consistency": "Actual multi-query observation; immutable event chain; not atomic read snapshot"}, nil
}
func (r Repo) Admission(ctx context.Context, candidate, metadata Map) (Map, error) {
	body := M(candidate["body"])
	if len(M(body["necessary_conditions"])) == 0 || len(M(body["scope"])) == 0 {
		return nil, ErrInvalid
	}
	source, e := r.Required(ctx, "SourceVerification", S(metadata["source_id"]))
	if e != nil || source["run_id"] != candidate["run_id"] || source["origin"] == "external_unverified" || metadata["strength"] != "BOUNDED_SUPPORT_NOT_CAUSAL" {
		return nil, ErrInvalid
	}
	facts := M(source["facts"])
	required := map[string]bool{}
	for _, scope := range []Map{M(body["necessary_conditions"]), M(body["scope"]), M(metadata["scope"])} {
		for k := range scope {
			required[k] = true
		}
		relation, _ := ScopeRelation(facts, scope)
		if len(scope) == 0 || relation != "MATCH" {
			return nil, ErrInvalid
		}
	}
	for _, key := range A(body["unknown_fields"]) {
		if required[S(key)] {
			return nil, ErrInvalid
		}
	}
	reviewed := M(metadata["scope"])
	for key, allowed := range M(body["scope"]) {
		if !has(reviewed, key) {
			return nil, ErrInvalid
		}
		for _, v := range A(reviewed[key]) {
			if !contains(allowed, v) {
				return nil, ErrInvalid
			}
		}
	}
	if exclusions := M(body["inapplicable_conditions"]); len(exclusions) > 0 {
		relation, _ := ScopeRelation(facts, exclusions)
		if relation != "UNRELATED" {
			return nil, ErrInvalid
		}
	}
	outcome, e := r.Required(ctx, "VerifiedOutcome", S(source["outcome_id"]))
	if e != nil || outcome["verdict"] != "PASS" || outcome["run_id"] != source["run_id"] {
		return nil, ErrInvalid
	}
	if e = r.RequireEdge(ctx, "HAS_SOURCE_VERIFICATION", "Candidate", S(candidate["id"]), "SourceVerification", S(source["id"])); e != nil {
		return nil, e
	}
	return source, nil
}
func (r Repo) Transition(ctx context.Context, id, state, expected, key, reason string, grant ReviewGrant, metadata Map) (Map, error) {
	if e := grant.Check(); e != nil {
		return nil, e
	}
	if !publicText(reason, 4000) || !validLocal(key, 64) || !shaPattern.MatchString(expected) || !subset(metadata, "source_id scope strength experience_id superseded_by") {
		return nil, ErrInvalid
	}
	if metadata == nil {
		metadata = Map{}
	}
	if has(metadata, "scope") {
		if e := ValidateScope(metadata["scope"]); e != nil {
			return nil, e
		}
	}
	if has(metadata, "strength") && metadata["strength"] != "BOUNDED_SUPPORT_NOT_CAUSAL" {
		return nil, ErrInvalid
	}
	eventID := "candidate-event:" + H(id) + ":" + key
	request := Map{"candidate_id": id, "state": state, "expected_head_sha256": expected, "reason": reason, "principal": grant.Principal, "expires_at": grant.ExpiresAt, "metadata": metadata}
	existing, e := r.Get(ctx, "CandidateEvent", eventID)
	if e != nil {
		return nil, e
	}
	if existing != nil {
		if existing["request_sha256"] != H(request) {
			return nil, ErrConflict
		}
		return Map{"event": existing, "idempotent_replay": true, "state_at_event": existing["to_state"]}, nil
	}
	view, e := r.Inspect(ctx, id)
	if e != nil {
		return nil, e
	}
	head := M(view["head"])
	if H(head) != expected || !transitions[S(head["state"])][state] {
		return nil, ErrConflict
	}
	if state == "ADMITTED_BOUNDED" {
		if _, e = r.Admission(ctx, M(view["candidate"]), metadata); e != nil {
			return nil, e
		}
	}
	if state == "PUBLISHING" || state == "PUBLISHED" {
		admissions := []Map{}
		for _, v := range A(view["events"]) {
			if M(v)["to_state"] == "ADMITTED_BOUNDED" {
				admissions = append(admissions, M(v))
			}
		}
		if len(admissions) != 1 {
			return nil, ErrInvalid
		}
		if _, e = r.Admission(ctx, M(view["candidate"]), M(admissions[0]["metadata"])); e != nil {
			return nil, e
		}
	}
	event := Map{"id": eventID, "candidate_id": id, "from_state": head["state"], "to_state": state, "previous_event_id": head["event_id"], "sequence": I(head["sequence"]) + 1, "created_at": Now(), "request_sha256": H(request), "reason": reason, "authority": "TRUSTED_HOST_REVIEW", "principal": grant.Principal, "metadata": metadata}
	newHead := Clone(head)
	newHead["state"], newHead["sequence"], newHead["event_id"] = state, event["sequence"], eventID
	if e = r.Put(ctx, "CandidateEvent", event); e != nil {
		return nil, e
	}
	if e = r.PutEdge(ctx, "HAS_CANDIDATE_EVENT", "Candidate", id, "CandidateEvent", eventID, nil); e != nil {
		return nil, e
	}
	if e = r.PutEdge(ctx, "PREVIOUS_EVENT", "CandidateEvent", eventID, "CandidateEvent", S(head["event_id"]), nil); e != nil {
		return nil, e
	}
	if e = ValidateRecord("LifecycleHead", newHead); e != nil {
		return nil, e
	}
	if e = r.CASHead(ctx, S(head["id"]), expected, newHead); e != nil {
		return nil, e
	}
	return Map{"event": event, "idempotent_replay": false, "state_at_event": state}, nil
}
func (r Repo) ImportExperience(ctx context.Context, experience, rule Map, revisionID string) error {
	premises := A(rule["premises"])
	if len(premises) == 0 {
		return ErrInvalid
	}
	record := Clone(rule)
	delete(record, "premises")
	ids := map[string]bool{}
	for _, v := range premises {
		p := M(v)
		if e := ValidateRecord("Premise", p); e != nil {
			return e
		}
		if ids[S(p["id"])] {
			return ErrInvalid
		}
		ids[S(p["id"])] = true
	}
	record["premise_ids"], record["premise_count"] = sortedSet(ids), len(ids)
	eid := S(experience["id"])
	if revisionID == "" {
		revisionID = eid + "/revision/initial"
	}
	revision := Map{"id": revisionID, "experience_id": eid, "created_at": defaultValue(experience, "created_at", "UNAVAILABLE"), "revision_reason": "initial_verified_history_import", "attribution": "UNKNOWN"}
	for _, row := range []struct {
		label string
		value Map
	}{{"Experience", experience}, {"ExperienceRevision", revision}, {"Rule", record}} {
		if e := r.Put(ctx, row.label, row.value); e != nil {
			return e
		}
	}
	if e := r.PutEdge(ctx, "HAS_REVISION", "Experience", eid, "ExperienceRevision", revisionID, nil); e != nil {
		return e
	}
	if e := r.PutEdge(ctx, "USES_RULE", "ExperienceRevision", revisionID, "Rule", S(record["id"]), nil); e != nil {
		return e
	}
	for _, v := range premises {
		p := M(v)
		if e := r.Put(ctx, "Premise", p); e != nil {
			return e
		}
		if e := r.PutEdge(ctx, "REQUIRES", "Rule", S(record["id"]), "Premise", S(p["id"]), nil); e != nil {
			return e
		}
	}
	return nil
}
func (r Repo) AttachEvidence(ctx context.Context, eid, rid, relation string, evidence, outcome, context, task Map) error {
	if !stringSet("SUPPORTED_BY COUNTEREXAMPLE OBSERVED_OUTCOME")[relation] {
		return ErrInvalid
	}
	if _, e := r.Required(ctx, "Experience", eid); e != nil {
		return e
	}
	rev, e := r.Required(ctx, "ExperienceRevision", rid)
	if e != nil || rev["experience_id"] != eid {
		return ErrInvalid
	}
	if e = r.RequireEdge(ctx, "HAS_REVISION", "Experience", eid, "ExperienceRevision", rid); e != nil {
		return e
	}
	if e = NormalizeContext(M(context["facts"]), false); e != nil {
		return e
	}
	if (relation == "SUPPORTED_BY" && outcome["verdict"] != "PASS") || (relation == "COUNTEREXAMPLE" && outcome["verdict"] != "FAIL") || defaultValue(evidence, "source_run_id", outcome["run_id"]) != outcome["run_id"] {
		return ErrInvalid
	}
	for _, row := range []struct {
		label string
		p     Map
	}{{"Evidence", evidence}, {"VerifiedOutcome", outcome}, {"Context", context}, {"Task", task}} {
		if e = ValidateRecord(row.label, row.p); e != nil {
			return e
		}
	}
	for _, row := range []struct {
		label string
		p     Map
	}{{"Evidence", evidence}, {"VerifiedOutcome", outcome}, {"Context", context}, {"Task", task}} {
		if e = r.Put(ctx, row.label, row.p); e != nil {
			return e
		}
	}
	for _, edge := range [][5]string{{relation, "ExperienceRevision", rid, "Evidence", S(evidence["id"])}, {"VERIFIES", "Evidence", S(evidence["id"]), "VerifiedOutcome", S(outcome["id"])}, {"IN_CONTEXT", "VerifiedOutcome", S(outcome["id"]), "Context", S(context["id"])}, {"FOR_TASK", "Context", S(context["id"]), "Task", S(task["id"])}} {
		if e = r.PutEdge(ctx, edge[0], edge[1], edge[2], edge[3], edge[4], nil); e != nil {
			return e
		}
	}
	return nil
}
func (r Repo) Publish(ctx context.Context, id, expected, key, reason string, grant ReviewGrant) (Map, error) {
	if e := grant.Check(); e != nil {
		return nil, e
	}
	view, e := r.Inspect(ctx, id)
	if e != nil {
		return nil, e
	}
	eid := "experience:published:" + H(id)
	state := S(M(view["head"])["state"])
	if state == "ADMITTED_BOUNDED" {
		if _, e = r.Transition(ctx, id, "PUBLISHING", expected, key+"-begin", reason, grant, Map{"experience_id": eid}); e != nil {
			return nil, e
		}
		view, e = r.Inspect(ctx, id)
		if e != nil {
			return nil, e
		}
	} else if state == "PUBLISHED" {
		allowed, e := r.PublicationAllowed(ctx, id, eid)
		if e != nil {
			return nil, e
		}
		if !allowed {
			return nil, ErrConflict
		}
		return Map{"status": "PUBLISHED", "experience_id": eid, "candidate_id": id, "idempotent_replay": true}, nil
	} else if state != "PUBLISHING" || view["head_sha256"] != expected {
		return nil, ErrConflict
	}
	candidate := M(view["candidate"])
	var admission Map
	for _, v := range A(view["events"]) {
		if M(v)["to_state"] == "ADMITTED_BOUNDED" {
			if admission != nil {
				return nil, ErrInvalid
			}
			admission = M(v)
		}
	}
	if admission == nil {
		return nil, ErrInvalid
	}
	source, e := r.Admission(ctx, candidate, M(admission["metadata"]))
	if e != nil {
		return nil, e
	}
	body := M(candidate["body"])
	origin := source["origin"]
	created := M(A(view["events"])[len(A(view["events"]))-1])["created_at"]
	rid := eid + "/revision/initial"
	limits := append([]any{}, A(body["limitations"])...)
	limits = append(limits, "Bounded support, causal benefit UNKNOWN")
	experience := Map{"id": eid, "strategy": body["strategy"], "title": body["title"], "public_summary": body["public_summary"], "source_type": origin, "created_at": created, "limitations": limits, "origin_run_id": source["run_id"], "origin_patch_sha256": source["submission_sha256"], "publication_candidate_id": id}
	conditions := Clone(M(body["necessary_conditions"]))
	for k, v := range M(M(admission["metadata"])["scope"]) {
		allowed := A(v)
		if old, ok := conditions[k]; ok {
			filtered := []any{}
			for _, x := range allowed {
				if contains(old, x) {
					filtered = append(filtered, x)
				}
			}
			allowed = filtered
			if len(allowed) == 0 {
				return nil, ErrInvalid
			}
		}
		conditions[k] = allowed
	}
	premises := []any{}
	for _, k := range keys(conditions) {
		premises = append(premises, Map{"id": "premise:" + H([]any{id, k}), "fact_key": k, "allowed_values": conditions[k], "required": true})
	}
	rule := Map{"id": "rule:" + H(id), "version": CandidateVersion, "public_description": "Host-reviewed factual conditions", "premises": premises}
	if e = r.ImportExperience(ctx, experience, rule, rid); e != nil {
		return nil, e
	}
	evidence := Map{"id": "evidence:candidate:" + H(id), "source_type": origin, "public_summary": "Host verified a submitted engineering artifact in the declared factual scope; attribution UNKNOWN.", "source_run_id": source["run_id"], "created_at": created, "attribution": "UNKNOWN"}
	context := Map{"id": "context:candidate:" + H(id), "facts": source["facts"], "source_type": origin}
	task := Map{"id": "task:candidate:" + H(id), "public_title": "Independently evaluated source submission"}
	contexts, e := r.targets(ctx, "VerifiedOutcome", S(source["outcome_id"]), "IN_CONTEXT", "Context")
	if e != nil {
		return nil, e
	}
	if len(contexts) > 0 {
		if len(contexts) != 1 {
			return nil, ErrConflict
		}
		tasks, e := r.targets(ctx, "Context", S(contexts[0]["id"]), "FOR_TASK", "Task")
		if e != nil || len(tasks) != 1 {
			return nil, ErrConflict
		}
		context, task = contexts[0], tasks[0]
		if !codec.Equal(context["facts"], source["facts"]) {
			return nil, ErrInvalid
		}
	}
	outcome, e := r.Required(ctx, "VerifiedOutcome", S(source["outcome_id"]))
	if e != nil {
		return nil, e
	}
	if e = r.AttachEvidence(ctx, eid, rid, "SUPPORTED_BY", evidence, outcome, context, task); e != nil {
		return nil, e
	}
	if e = r.PutEdge(ctx, "PUBLISHED_FROM", "Experience", eid, "Candidate", id, nil); e != nil {
		return nil, e
	}
	if _, e = r.Transition(ctx, id, "PUBLISHED", S(view["head_sha256"]), key+"-complete", reason, grant, Map{"experience_id": eid}); e != nil {
		return nil, e
	}
	return Map{"status": "PUBLISHED", "experience_id": eid, "candidate_id": id, "causal_benefit": "UNKNOWN"}, nil
}
func (r Repo) PublicationAllowed(ctx context.Context, id, eid string) (bool, error) {
	view, e := r.Inspect(ctx, id)
	if e != nil {
		return false, e
	}
	if M(view["head"])["state"] != "PUBLISHED" {
		return false, nil
	}
	events := A(view["events"])
	last := M(events[len(events)-1])
	if M(last["metadata"])["experience_id"] != eid {
		return false, ErrConflict
	}
	if e = r.RequireEdge(ctx, "PUBLISHED_FROM", "Experience", eid, "Candidate", id); e != nil {
		return false, e
	}
	return true, nil
}
