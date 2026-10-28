package native

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"strings"
	"time"
)

func (r *Runtime) prepareRecall(ctx context.Context, op string, args domain.Map) (*domain.RecallPlan, error) {
	plan, err := r.prepareSemanticRecall(ctx, op, args)
	if err != nil || r.reranker == nil || (op != "resolve_experience" && op != "query") {
		return plan, err
	}
	_, query, _, _, err := domain.ValidateRecallInput(args, r.facts)
	if err != nil {
		return nil, engine.ErrInvalid
	}
	if strings.TrimSpace(query) == "" {
		return plan, nil
	}
	if plan == nil {
		plan = &domain.RecallPlan{Label: "Experience", Query: query, Metadata: domain.Map{"semantic_recall": "DISABLED"}}
	}
	config := r.reranker.Config()
	meta := plan.Metadata
	meta["reranker"], meta["reranker_provider"], meta["reranker_model"], meta["reranker_revision"] = "UNAVAILABLE", "TEI_LOOPBACK", config.Model, config.Revision
	meta["reranker_identity"] = "NOT_VERIFIED"
	meta["reranker_score_semantics"], meta["reranker_min_score"], meta["reranker_on_failure"] = "RAW_LOGIT_NOT_SUCCESS_PROBABILITY", *config.MinScore, config.OnFailure
	ids := plan.IDs
	if !plan.Ready {
		hits, _, e := r.store.Read().Recall(ctx, "Experience", query, config.MaxCandidates+1, 0)
		if e != nil {
			return nil, engine.ErrUnknown
		}
		ids = []string{}
		for _, hit := range hits {
			ids = append(ids, hit.ID)
		}
	}
	meta["reranker_candidates_truncated"] = len(ids) > config.MaxCandidates
	if len(ids) > config.MaxCandidates {
		ids = ids[:config.MaxCandidates]
	}
	docs, e := r.store.Read().RecallDocumentsByIDs(ctx, ids)
	if e != nil {
		return nil, engine.ErrUnknown
	}
	if len(docs) == 0 {
		plan.Ready = true
		plan.IDs = []string{}
		meta["reranker"] = "NOT_RUN_NO_CANDIDATES"
		meta["reranker_scored"] = 0
		return plan, nil
	}
	start := time.Now()
	ranked, e := r.reranker.Rank(ctx, query, docs)
	meta["reranker_elapsed_ms"] = time.Since(start).Milliseconds()
	if ctx.Err() != nil {
		return nil, engine.ErrNotDispatched
	}
	if e != nil {
		meta["reranker_failure"] = "PROVIDER_UNAVAILABLE_OR_INVALID"
		if config.OnFailure == "ABSTAIN" {
			plan.Ready = true
			plan.IDs = []string{}
			meta["reranker_fallback"] = "EMPTY_CANDIDATES"
		} else {
			meta["reranker_fallback"] = "PRE_RERANK_LANES"
		}
		return plan, nil
	}
	plan.Ready = true
	plan.IDs = ranked.IDs
	meta["reranker"], meta["reranker_scored"], meta["reranker_rejected"], meta["reranker_input_clipped"] = "READY", ranked.Scored, ranked.Rejected, ranked.InputClipped
	meta["reranker_identity"] = "SERVICE_REPORTED_ID_AND_REVISION_NOT_WEIGHT_ATTESTATION"
	method := domain.S(meta["method"])
	if method == "" {
		method = "SQLITE_FTS5_BM25_PUBLIC_NARRATIVES"
	}
	meta["method"] = method + "_TEI_RAW_RERANK"
	return plan, nil
}

func (r *Runtime) prepareSemanticRecall(ctx context.Context, op string, args domain.Map) (*domain.RecallPlan, error) {
	if r.semantic == nil || (op != "resolve_experience" && op != "query") {
		return nil, nil
	}
	_, query, _, _, err := domain.ValidateRecallInput(args, r.facts)
	if err != nil {
		return nil, engine.ErrInvalid
	}
	if strings.TrimSpace(query) == "" {
		return nil, nil
	}
	plan := &domain.RecallPlan{Label: "Experience", Query: query, Metadata: domain.Map{"semantic_recall": "UNAVAILABLE", "semantic_provider": "OLLAMA_LOOPBACK", "semantic_model": r.semantic.Config().Model, "semantic_identity": "PROTECTED_MODEL_TAG_NOT_WEIGHT_ATTESTATION"}}
	docs, more, err := r.store.Read().RecallDocuments(ctx, "Experience", r.semantic.Config().MaxDocuments)
	if err != nil {
		return nil, engine.ErrUnknown
	}
	plan.Metadata["semantic_corpus_truncated"] = more
	start := time.Now()
	ranked, err := r.semantic.Rank(ctx, query, docs, 50)
	plan.Metadata["semantic_elapsed_ms"] = time.Since(start).Milliseconds()
	if ctx.Err() != nil {
		return nil, engine.ErrNotDispatched
	}
	if err != nil {
		plan.Metadata["semantic_failure"] = "PROVIDER_UNAVAILABLE_OR_INVALID"
		return plan, nil
	}
	lexical, _, err := r.store.Read().Recall(ctx, "Experience", query, 50, 0)
	if err != nil {
		return nil, engine.ErrUnknown
	}
	ids := []string{}
	for _, h := range lexical {
		ids = append(ids, h.ID)
	}
	plan.IDs = retrieval.Fuse(ids, ranked.IDs)
	plan.Ready = true
	plan.Metadata["method"] = "SQLITE_FTS5_OLLAMA_COSINE_RRF"
	plan.Metadata["semantic_recall"] = "READY"
	plan.Metadata["semantic_documents"] = ranked.Documents
	plan.Metadata["semantic_cache_hits"] = ranked.CacheHits
	plan.Metadata["semantic_input_clipped"] = ranked.InputClipped
	plan.Metadata["rank_window_per_lane"] = 50
	return plan, nil
}
