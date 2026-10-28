package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"strings"
)

func (r Repo) RecallObservations(ctx context.Context, query string, limit int) (Map, error) {
	if len(query) > 4000 || limit < 1 || limit > 20 || (strings.TrimSpace(query) != "" && !publicText(query, 1000)) {
		return nil, ErrInvalid
	}
	hits, expanded, err := r.Recall(ctx, "Candidate", query, limit+1, 0)
	if err != nil {
		return nil, err
	}
	out := Map{"status": "AVAILABLE", "query": query, "observations": []any{}, "authority": "UNTRUSTED_OBSERVATIONS_ONLY", "applicability": "NOT_EVALUATED", "adoption": "UNKNOWN", "causal_benefit": "UNKNOWN", "limit": limit, "ordering": "SQLITE_FTS5_BM25_PUBLIC_NARRATIVES", "aliases": values(expanded), "semantic_recall": "NOT_IMPLEMENTED", "more_matches": len(hits) > limit, "projection": "BOUNDED_PUBLIC_EXCERPTS", "assurance": "Investigative leads only; these claims never establish APPLY or a verified outcome."}
	_, _, limited := retrieval.Query(query)
	out["query_terms_truncated"] = limited
	groups, required, coverageLimited := retrieval.Coverage(query)
	out["lexical_coverage"] = Map{"policy": retrieval.CoveragePolicy, "concepts": len(groups), "minimum_matches": required, "truncated": coverageLimited, "applies_to": "LEXICAL_LANE_ONLY"}
	out["summary_transport_budget_bytes"] = SummaryTransportBytes
	observations := []any{}
	for _, hit := range hits {
		if len(observations) == limit {
			break
		}
		view, err := r.Inspect(ctx, hit.ID)
		if err != nil {
			return nil, err
		}
		p := M(view["candidate"])
		body := M(p["body"])
		feedback, err := r.observationUseSample(ctx, hit.ID)
		if err != nil {
			return nil, err
		}
		card := Map{"candidate_id": hit.ID, "run_id": p["run_id"], "body_sha256": p["body_sha256"], "state": M(view["head"])["state"], "title": excerpt(body["title"], 160), "public_summary": excerpt(body["public_summary"], 300), "strategy": excerpt(body["strategy"], 500), "authority": "UNTRUSTED_OBSERVATION", "applicability": "NOT_EVALUATED", "usage_feedback": feedback}
		sources, err := r.CaptureSummary(ctx, hit.ID, S(p["run_id"]))
		if err != nil {
			return nil, err
		}
		if sources != nil {
			card["capture_sources"] = sources
		}
		observations = append(observations, card)
		out["observations"] = observations
		raw, err := codec.Canonical(out)
		if err != nil {
			return nil, err
		}
		if len(raw) > SummaryBytes || !fitsSummaryTransport(raw) {
			out["observations"] = observations[:len(observations)-1]
			out["more_matches"] = true
			break
		}
	}
	return out, nil
}

// Bounded examples, not a popularity score or a verified exposure. Ordering by
// immutable ID is deterministic; it does not claim to show the newest reports.
func (r Repo) observationUseSample(ctx context.Context, candidate string) (Map, error) {
	rows, err := r.Repository.ExternalByKind(ctx, candidate, "", "OBSERVATION_USE_CLAIM", 3)
	if err != nil {
		return nil, err
	}
	reports := []any{}
	more := len(rows) > 2
	for _, row := range rows {
		if err = ValidateRecord("ExternalObservation", row); err != nil {
			return nil, err
		}
		if len(reports) == 2 {
			more = true
			break
		}
		if err = r.RequireEdge(ctx, "DERIVED_FROM", "ExternalObservation", S(row["id"]), "Candidate", candidate); err != nil {
			return nil, err
		}
		reports = append(reports, Map{"report_id": row["id"], "run_id": row["run_id"], "purpose": row["purpose"], "disposition": row["disposition"], "public_summary": excerpt(row["public_summary"], 400), "elapsed_seconds": row["elapsed_seconds"], "authority": "UNTRUSTED_USAGE_CLAIM"})
	}
	return Map{"reports": reports, "more_reports_possible": more, "ordering": "ID_NOT_RECENCY", "exposure": "NOT_VERIFIED", "adoption": "CLAIM_ONLY", "causal_benefit": "UNKNOWN"}, nil
}

func (r Repo) SearchObservations(ctx context.Context, query string, limit int) (Map, error) {
	if len(query) > 1000 || len(strings.Fields(query)) > 8 || limit < 1 || limit > 20 {
		return nil, ErrInvalid
	}
	rows, err := r.Repository.SearchObservations(ctx, query, limit)
	if err != nil {
		return nil, err
	}
	results := []any{}
	for _, p := range rows {
		public, err := PublicCandidate(p)
		if err != nil {
			return nil, err
		}
		view, err := r.Inspect(ctx, S(p["id"]))
		if err != nil {
			return nil, err
		}
		public["candidate_id"], public["run_id"], public["body_sha256"], public["state"] = p["id"], p["run_id"], p["body_sha256"], M(view["head"])["state"]
		public["authority"], public["applicability"] = "UNTRUSTED_OBSERVATION", "NOT_EVALUATED"
		sources, err := r.CaptureSummary(ctx, S(p["id"]), S(p["run_id"]))
		if err != nil {
			return nil, err
		}
		if sources != nil {
			public["capture_sources"] = sources
		}
		results = append(results, public)
	}
	return Map{"status": "AVAILABLE", "query": query, "observations": results, "authority": "UNTRUSTED_OBSERVATIONS_ONLY", "applicability": "NOT_EVALUATED", "adoption": "UNKNOWN", "causal_benefit": "UNKNOWN", "limit": limit, "ordering": "RECENT_MATCHES; literal public narrative keywords; not semantic confidence", "assurance": "Use only as investigative leads. Inspect and independently verify claims; these results never establish APPLY or a verified outcome."}, nil
}
