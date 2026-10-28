package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/google/uuid"
	"strings"
)

type Service struct {
	Repo      Repo
	Run       string
	Facts     Map
	Proposals bool
	Clock     func() string
	NewID     func() string
	Recall    *RecallPlan
}

func (s Service) now() string {
	if s.Clock != nil {
		return s.Clock()
	}
	return Now()
}
func (s Service) id() string {
	if s.NewID != nil {
		return s.NewID()
	}
	return uuid.NewString()
}
func (s Service) ResolveExperience(ctx context.Context, claims Map) (Map, error) {
	if e := NormalizeContext(claims, true); e != nil {
		return nil, e
	}
	for key, value := range claims {
		if FactState(s.Facts, key) == "KNOWN" && !codec.Equal(value, s.Facts[key]) {
			return nil, ErrInvalid
		}
	}
	result, e := s.Repo.Resolve(ctx, s.Facts, s.now(), true)
	if e != nil {
		return nil, e
	}
	return s.recordQuery(ctx, claims, result, false)
}

func (s Service) recordQuery(ctx context.Context, claims, result Map, compact bool) (Map, error) {
	queryID := "query:" + s.Run + ":" + s.id()
	if compact {
		if err := s.fitSummary(result, claims, queryID); err != nil {
			return nil, err
		}
	}
	contextID := "context:query:trusted-public:v1:" + H(s.Facts)
	if e := s.Repo.Put(ctx, "Context", Map{"id": contextID, "facts": s.Facts, "source_type": "trusted_public_environment"}); e != nil {
		return nil, e
	}
	ids := []any{}
	for _, v := range A(result["candidates"]) {
		ids = append(ids, M(v)["experience_id"])
	}
	query := Map{"id": queryID, "run_id": s.Run, "created_at": s.now(), "task_context": s.Facts, "pinned_public_context": s.Facts, "participant_claims": claims, "candidate_experience_ids": ids, "query_version": defaultValue(result, "query_version", "UNAVAILABLE"), "graph_snapshot_sha256": defaultValue(result, "graph_snapshot_sha256", "UNAVAILABLE"), "response_sha256": H(result), "authority": "scoped_broker_run", "context_authority": "TRUSTED_PINNED_PUBLIC_FACTS_ONLY", "participant_claims_status": "UNVERIFIED_NOT_USED_FOR_APPLICABILITY", "agent_thread_id": "UNAVAILABLE"}
	if retrieval := M(result["retrieval"]); retrieval != nil {
		query["task_query"], query["retrieval"] = retrieval["query"], Clone(retrieval)
		if compact {
			query["response_sha256"] = H(s.summary(result, claims, queryID))
		}
	}
	snapshots := M(result["query_snapshot_ids"])
	if len(snapshots) != len(ids) {
		return nil, ErrConflict
	}
	for _, id := range ids {
		sid := S(snapshots[S(id)])
		snapshot, e := s.Repo.Required(ctx, "QuerySnapshot", sid)
		if e != nil {
			return nil, e
		}
		content := M(snapshot["content"])
		if !codec.Equal(content["context"], s.Facts) || M(content["candidate"])["experience_id"] != id {
			return nil, ErrConflict
		}
	}
	query["query_snapshot_ids"], query["governance_evidence_sha256"], query["decision_engine_version"] = snapshots, defaultValue(result, "governance_evidence_sha256", "UNAVAILABLE"), defaultValue(result, "decision_engine_version", "UNAVAILABLE")
	if e := s.Repo.Put(ctx, "Query", query); e != nil {
		return nil, e
	}
	if e := s.Repo.PutEdge(ctx, "DERIVED_FROM", "Query", queryID, "Context", contextID, nil); e != nil {
		return nil, e
	}
	for _, id := range ids {
		if e := s.Repo.PutEdge(ctx, "CONSIDERED", "Query", queryID, "Experience", S(id), nil); e != nil {
			return nil, e
		}
	}
	for _, v := range snapshots {
		if e := s.Repo.PutEdge(ctx, "AT_SNAPSHOT", "Query", queryID, "QuerySnapshot", S(v), nil); e != nil {
			return nil, e
		}
	}
	result["query_id"], result["run_id"], result["query_record_sha256"], result["mcp_version"] = queryID, s.Run, H(query), MCPVersion
	result["context_authority"], result["pinned_public_context"], result["participant_claims"], result["participant_claims_status"] = "TRUSTED_PINNED_PUBLIC_FACTS_ONLY", s.Facts, claims, "UNVERIFIED_NOT_USED_FOR_APPLICABILITY"
	if compact {
		out := s.summary(result, claims, queryID)
		out["query_record_sha256"] = result["query_record_sha256"]
		return out, nil
	}
	return result, nil
}
func (s Service) Bundle(ctx context.Context, id, queryID string) (Map, error) {
	if !storage.ValidID(id) {
		return nil, ErrInvalid
	}
	if queryID != "" {
		query, e := s.Repo.Required(ctx, "Query", queryID)
		if e != nil || query["run_id"] != s.Run || !contains(query["candidate_experience_ids"], id) {
			return nil, ErrInvalid
		}
		sid := S(M(query["query_snapshot_ids"])[id])
		if sid == "" {
			return nil, ErrInvalid
		}
		if e = s.Repo.RequireEdge(ctx, "CONSIDERED", "Query", queryID, "Experience", id); e != nil {
			return nil, e
		}
		if e = s.Repo.RequireEdge(ctx, "AT_SNAPSHOT", "Query", queryID, "QuerySnapshot", sid); e != nil {
			return nil, e
		}
		snapshot, e := s.Repo.Required(ctx, "QuerySnapshot", sid)
		if e != nil {
			return nil, e
		}
		content := M(snapshot["content"])
		candidate := M(content["candidate"])
		if candidate["experience_id"] != id || !codec.Equal(content["context"], query["task_context"]) {
			return nil, ErrConflict
		}
		out := Clone(M(candidate["evidence_bundle"]))
		out["query_snapshot_id"], out["snapshot_mode"], out["as_of"] = sid, "IMMUTABLE_QUERY_REPLAY", content["as_of"]
		return out, nil
	}
	queries, e := s.Repo.List(ctx, "Query", storage.Filter{Run: s.Run, Limit: 4097})
	if e != nil {
		return nil, e
	}
	if len(queries) > 4096 {
		return nil, ErrInvalid
	}
	authorized := false
	for _, q := range queries {
		if contains(q["candidate_experience_ids"], id) {
			if e = s.Repo.RequireEdge(ctx, "CONSIDERED", "Query", S(q["id"]), "Experience", id); e != nil {
				return nil, e
			}
			authorized = true
		}
	}
	if !authorized {
		return nil, ErrInvalid
	}
	return s.Repo.Bundle(ctx, id)
}
func (s Service) RecordDecision(ctx context.Context, d Map) (Map, error) {
	if d == nil || !subset(d, "decision_id query_id experience_id decision reason verification_steps") {
		return nil, ErrInvalid
	}
	queryID, eid := S(d["query_id"]), S(d["experience_id"])
	query, e := s.Repo.Required(ctx, "Query", queryID)
	if e != nil || query["run_id"] != s.Run || !contains(query["candidate_experience_ids"], eid) {
		return nil, ErrInvalid
	}
	kind := S(d["decision"])
	steps, ok := defaultValue(d, "verification_steps", []any{}).([]any)
	if !stringSet("APPLY VERIFY ABSTAIN")[kind] || !text(d["reason"], 4000) || !ok || len(steps) > 32 {
		return nil, ErrInvalid
	}
	for _, v := range steps {
		if !text(v, 1000) {
			return nil, ErrInvalid
		}
	}
	if kind == "VERIFY" && len(steps) == 0 {
		return nil, ErrInvalid
	}
	id := S(d["decision_id"])
	if id == "" {
		id = "decision:" + s.Run + ":" + s.id()
	}
	if !storage.ValidID(id) || !strings.HasPrefix(id, "decision:"+s.Run+":") {
		return nil, ErrInvalid
	}
	existing, e := s.Repo.Get(ctx, "Decision", id)
	if e != nil {
		return nil, e
	}
	created := s.now()
	if existing != nil {
		created = S(existing["created_at"])
	}
	p := Map{"id": id, "run_id": s.Run, "query_id": queryID, "experience_id": eid, "decision": kind, "reason": d["reason"], "verification_steps": steps, "authority": "UNTRUSTED_PARTICIPANT_CLAIM", "adoption": "CLAIM_ONLY", "attribution": "UNKNOWN", "agent_thread_id": "UNAVAILABLE", "created_at": created}
	if len(M(query["query_snapshot_ids"])) > 0 {
		sid := S(M(query["query_snapshot_ids"])[eid])
		if e = s.Repo.RequireEdge(ctx, "CONSIDERED", "Query", queryID, "Experience", eid); e != nil {
			return nil, e
		}
		if e = s.Repo.RequireEdge(ctx, "AT_SNAPSHOT", "Query", queryID, "QuerySnapshot", sid); e != nil {
			return nil, e
		}
		snapshot, e := s.Repo.Required(ctx, "QuerySnapshot", sid)
		if e != nil {
			return nil, e
		}
		content := M(snapshot["content"])
		if M(content["candidate"])["experience_id"] != eid || !codec.Equal(content["context"], query["task_context"]) {
			return nil, ErrConflict
		}
		p["query_snapshot_id"], p["decision_engine_version"] = sid, defaultValue(query, "decision_engine_version", "UNAVAILABLE")
	}
	if e = s.Repo.Put(ctx, "Decision", p); e != nil {
		return nil, e
	}
	if e = s.Repo.PutEdge(ctx, "RESPONDS_TO", "Decision", id, "Query", queryID, nil); e != nil {
		return nil, e
	}
	if e = s.Repo.PutEdge(ctx, "DECIDED", "Decision", id, "Experience", eid, nil); e != nil {
		return nil, e
	}
	return Map{"status": "RECORDED_UNTRUSTED", "decision_id": id, "run_id": s.Run, "query_id": queryID, "experience_id": eid, "payload_sha256": H(p), "attribution": "UNKNOWN", "trusted_outcome": "NOT_SUBMITTED", "mcp_version": MCPVersion}, nil
}
func (s Service) Call(ctx context.Context, operation string, args Map) (Map, error) {
	switch operation {
	case "read_observation_sources":
		if !subset(args, "candidate_id after limit") || !has(args, "candidate_id") {
			return nil, ErrInvalid
		}
		limit := 10
		if has(args, "limit") {
			if !boundedInteger(args["limit"], 20) {
				return nil, ErrInvalid
			}
			limit = I(args["limit"])
		}
		return s.ReadObservationSources(ctx, S(args["candidate_id"]), S(args["after"]), limit)
	case "search_observations":
		if !subset(args, "query limit mode") || !has(args, "query") {
			return nil, ErrInvalid
		}
		query, ok := args["query"].(string)
		if !ok {
			return nil, ErrInvalid
		}
		limit := 10
		if has(args, "limit") {
			if !boundedInteger(args["limit"], 20) {
				return nil, ErrInvalid
			}
			limit = I(args["limit"])
		}
		switch S(defaultValue(args, "mode", "literal")) {
		case "literal":
			return s.Repo.SearchObservations(ctx, query, limit)
		case "ranked":
			return s.Repo.RecallObservations(ctx, query, limit)
		default:
			return nil, ErrInvalid
		}
	case "resolve_experience":
		return s.ResolveTaskExperience(ctx, args)
	case "build_evidence_bundle":
		if !subset(args, "experience_id query_id") || !has(args, "experience_id") {
			return nil, ErrInvalid
		}
		return s.Bundle(ctx, S(args["experience_id"]), S(args["query_id"]))
	case "record_decision":
		if !exact(args, "decision") {
			return nil, ErrInvalid
		}
		return s.RecordDecision(ctx, M(args["decision"]))
	case "record_observation_use":
		if !exact(args, "report") {
			return nil, ErrInvalid
		}
		return s.RecordObservationUse(ctx, M(args["report"]))
	case "propose_experience":
		if !s.Proposals || !exact(args, "proposal") {
			return nil, ErrInvalid
		}
		return s.Repo.Propose(ctx, s.Run, M(args["proposal"]))
	default:
		return nil, ErrInvalid
	}
}
