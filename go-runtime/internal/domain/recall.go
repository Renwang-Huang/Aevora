package domain

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"strings"
)

const SummaryBytes = 32768
const SummaryTransportBytes = 131072

// Cover the SDK's structured JSON plus serialized text fallback and HTML
// escaping. The Host still validates its actual final SDK/RPC encoding before
// commit; this conservative projection budget prevents avoidable rollbacks.
func fitsSummaryTransport(raw []byte) bool {
	encoded, err := json.Marshal(Map{"structuredContent": json.RawMessage(raw), "content": []any{Map{"type": "text", "text": string(raw)}}})
	return err == nil && len(encoded)+1024 <= SummaryTransportBytes
}

// RecallPlan is prepared by the trusted native runtime outside SQLite writes.
// Its IDs still require current graph/lifecycle/WHEN/WHY validation.
type RecallPlan struct {
	Label, Query string
	IDs          []string
	Ready        bool
	Metadata     Map
}

// ResolveTaskExperience accepts relevance text separately from applicability
// claims. Text selects candidates; only pinned facts enter WHEN/WHY.
func (s Service) ResolveTaskExperience(ctx context.Context, args Map) (Map, error) {
	claims, query, limit, detail, err := ValidateRecallInput(args, s.Facts)
	if err != nil {
		return nil, err
	}
	return s.resolveTask(ctx, claims, query, limit, detail)
}

// ValidateRecallInput also runs before sending public text to an optional
// embedding adapter. Invalid or private input must not reach that adapter.
func ValidateRecallInput(args, facts Map) (Map, string, int, string, error) {
	if !subset(args, "task_context query limit detail") || !has(args, "task_context") {
		return nil, "", 0, "", ErrInvalid
	}
	claims, ok := args["task_context"].(map[string]any)
	if !ok || NormalizeContext(claims, true) != nil {
		return nil, "", 0, "", ErrInvalid
	}
	for key, value := range claims {
		if FactState(facts, key) == "KNOWN" && !codec.Equal(value, facts[key]) {
			return nil, "", 0, "", ErrInvalid
		}
	}
	input := defaultValue(args, "query", "")
	if input == nil {
		input = ""
	}
	query, ok := input.(string)
	if !ok || len(query) > 4000 || (strings.TrimSpace(query) != "" && !publicText(query, 1000)) {
		return nil, "", 0, "", ErrInvalid
	}
	limit := 5
	if has(args, "limit") {
		if !boundedInteger(args["limit"], 20) || I(args["limit"]) < 1 {
			return nil, "", 0, "", ErrInvalid
		}
		limit = I(args["limit"])
	}
	detail := S(defaultValue(args, "detail", "summary"))
	if detail != "summary" && detail != "full" {
		return nil, "", 0, "", ErrInvalid
	}
	return claims, query, limit, detail, nil
}

func (s Service) resolveTask(ctx context.Context, claims Map, query string, limit int, detail string) (Map, error) {
	ids, expanded := []string{}, []string{}
	examined, more := 0, false
	// No task text must not silently become a recommendation for every task
	// that happens to run on the same Host. Legacy trusted Resolve remains a
	// separate conditions-only diagnostic for source/reference maintenance.
	if strings.TrimSpace(query) != "" {
		for offset := 0; offset < 1000; offset += 50 {
			var hits []storage.RecallHit
			var aliases []string
			var err error
			if s.Recall != nil && s.Recall.Ready {
				if s.Recall.Label != "Experience" || s.Recall.Query != query {
					return nil, ErrInvalid
				}
				end := offset + 50
				if end > len(s.Recall.IDs) {
					end = len(s.Recall.IDs)
				}
				if offset < end {
					for _, id := range s.Recall.IDs[offset:end] {
						hits = append(hits, storage.RecallHit{ID: id})
					}
				}
				_, aliases, _ = retrieval.Query(query)
			} else {
				hits, aliases, err = s.Repo.Recall(ctx, "Experience", query, 50, offset)
			}
			if err != nil {
				return nil, err
			}
			expanded = aliases
			for _, hit := range hits {
				examined++
				p, err := s.Repo.Required(ctx, "Experience", hit.ID)
				if err != nil {
					return nil, err
				}
				if candidate := S(p["publication_candidate_id"]); candidate != "" {
					allowed, err := s.Repo.PublicationAllowed(ctx, candidate, hit.ID)
					if err != nil {
						return nil, err
					}
					if !allowed {
						continue
					}
				}
				if len(ids) == limit {
					more = true
					break
				}
				ids = append(ids, hit.ID)
			}
			if more || len(hits) < 50 {
				break
			}
			if offset == 950 {
				more = true
			}
		}
	}
	result, err := s.Repo.resolveIDs(ctx, s.Facts, s.now(), true, ids)
	if err != nil {
		return nil, err
	}
	state := "RANKED"
	if strings.TrimSpace(query) == "" {
		state = "TASK_QUERY_REQUIRED"
	}
	result["retrieval"] = Map{"schema_version": "aevora.recall/1", "query": query, "query_authority": "UNTRUSTED_RELEVANCE_ONLY", "method": "SQLITE_FTS5_BM25_PUBLIC_NARRATIVES", "aliases": values(expanded), "alias_version": "engineering-lexicon/1", "status": state, "limit": limit, "examined": examined, "more_matches": more, "semantic_recall": "DISABLED", "summary_byte_budget": SummaryBytes, "output_truncated": false}
	if s.Recall != nil {
		for key, value := range s.Recall.Metadata {
			M(result["retrieval"])[key] = value
		}
	}
	_, _, limited := retrieval.Query(query)
	M(result["retrieval"])["query_terms_truncated"] = limited
	groups, required, coverageLimited := retrieval.Coverage(query)
	M(result["retrieval"])["lexical_coverage"] = Map{"policy": retrieval.CoveragePolicy, "concepts": len(groups), "minimum_matches": required, "truncated": coverageLimited, "applies_to": "LEXICAL_LANE_ONLY", "assurance": "LEXICAL_FILTER_NOT_ANSWERABILITY_OR_APPLICABILITY; unknown Han is not translated"}
	M(result["retrieval"])["summary_transport_budget_bytes"] = SummaryTransportBytes
	return s.recordQuery(ctx, claims, result, detail == "summary")
}

func excerpt(value any, size int) string {
	text := S(value)
	runes := []rune(text)
	if len(runes) > size {
		return string(runes[:size]) + "…"
	}
	return text
}

func (s Service) summary(result, claims Map, queryID string) Map {
	cards := []any{}
	for _, raw := range A(result["candidates"]) {
		c := M(raw)
		experience := M(M(c["evidence_bundle"])["experience"])
		steps := []any{}
		for _, step := range A(c["verification_steps"]) {
			if len(steps) == 3 {
				break
			}
			steps = append(steps, excerpt(step, 160))
		}
		limitations := []any{}
		for _, item := range A(experience["limitations"]) {
			if len(limitations) == 2 {
				break
			}
			limitations = append(limitations, excerpt(item, 200))
		}
		cards = append(cards, Map{"experience_id": c["experience_id"], "title": excerpt(experience["title"], 160), "public_summary": excerpt(experience["public_summary"], 300), "strategy": excerpt(c["strategy"], 500), "decision": c["decision"], "reason": excerpt(c["reason"], 240), "current_operation_coverage": c["current_operation_coverage"], "verification_steps": steps, "limitations": limitations, "query_snapshot_id": c["query_snapshot_id"], "projection": "BOUNDED_EXCERPTS; use build_evidence_bundle with query_id for complete conditions/evidence"})
	}
	return Map{"status": result["status"], "context": s.Facts, "candidates": cards, "query_id": queryID, "run_id": s.Run, "query_version": result["query_version"], "decision_engine_version": RuleVersion, "mcp_version": MCPVersion, "retrieval": result["retrieval"], "graph_snapshot_sha256": result["graph_snapshot_sha256"], "governance_evidence_sha256": result["governance_evidence_sha256"], "context_authority": "TRUSTED_PINNED_PUBLIC_FACTS_ONLY", "pinned_public_context": s.Facts, "participant_claims": claims, "participant_claims_status": "UNVERIFIED_NOT_USED_FOR_APPLICABILITY", "attribution": "UNKNOWN", "adoption": "UNKNOWN", "causal_benefit": "UNKNOWN", "assurance": "Lexical relevance is not applicability or verified utility. Review complete conditions and evidence before using a principle."}
}

func (s Service) fitSummary(result, claims Map, queryID string) error {
	for {
		raw, err := codec.Canonical(s.summary(result, claims, queryID))
		if err != nil {
			return err
		}
		// Reserve space for the final query-record digest and JSON field name.
		if len(raw)+128 <= SummaryBytes && fitsSummaryTransport(raw) {
			return nil
		}
		candidates := A(result["candidates"])
		if len(candidates) == 0 {
			return ErrInvalid
		}
		removed := S(M(candidates[len(candidates)-1])["experience_id"])
		result["candidates"] = candidates[:len(candidates)-1]
		delete(M(result["query_snapshot_ids"]), removed)
		snapshots, governance := Map{}, Map{}
		for _, raw := range A(result["candidates"]) {
			c := M(raw)
			snapshots[S(c["experience_id"])], governance[S(c["experience_id"])] = c["retrieval_snapshot_sha256"], c["governance_evidence_sha256"]
		}
		result["graph_snapshot_sha256"], result["governance_evidence_sha256"] = H(snapshots), H(governance)
		M(result["retrieval"])["output_truncated"], M(result["retrieval"])["more_matches"] = true, true
	}
}
