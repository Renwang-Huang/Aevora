package native

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/transfer"
)

func keys(args domain.Map, names ...string) bool {
	if len(args) != len(names) {
		return false
	}
	for _, name := range names {
		if _, ok := args[name]; !ok {
			return false
		}
	}
	return true
}
func (r *Runtime) manage(ctx context.Context, repo domain.Repo, operation string, args domain.Map, plan *domain.RecallPlan) (domain.Map, error) {
	switch operation {
	case "memory-sources":
		if !keys(args, "candidate_id", "project", "after", "limit") || !domain.ValidSourcePageLimit(args["limit"]) {
			return nil, domain.ErrInvalid
		}
		return repo.TaskCandidateSources(ctx, domain.S(args["candidate_id"]), domain.S(args["after"]), domain.I(args["limit"]), domain.S(args["project"]))
	case "memory-source-info":
		if !keys(args, "source_id", "project") {
			return nil, domain.ErrInvalid
		}
		p, e := repo.Required(ctx, "ExternalObservation", domain.S(args["source_id"]))
		if e != nil || domain.M(p["event"])["project"] != args["project"] {
			return nil, domain.ErrInvalid
		}
		return domain.Map{"event": p["event"]}, nil
	case "memory-json-projection":
		return repo.JSONCheckProjection(ctx, args, true)
	case "memory-check-unavailable":
		if !keys(args, "candidate_id", "project") {
			return nil, domain.ErrInvalid
		}
		return repo.MemoryCheckUnavailable(ctx, domain.S(args["candidate_id"]), domain.S(args["project"]), true)
	case "memory-check-guard":
		if !keys(args, "candidate_id", "project", "basis", "record") {
			return nil, domain.ErrInvalid
		}
		return repo.MemoryCheckGuard(ctx, domain.S(args["candidate_id"]), domain.S(args["project"]), domain.S(args["basis"]), domain.B(args["record"]))
	case "memory-state":
		if !(keys(args, "project") || keys(args, "project", "after")) {
			return nil, domain.ErrInvalid
		}
		return repo.Repository.MemoryOverviewPage(ctx, domain.S(args["project"]), domain.S(args["after"]))
	case "memory-revoke-source":
		if !keys(args, "source_id", "project") {
			return nil, domain.ErrInvalid
		}
		return repo.RevokeTaskSource(ctx, domain.S(args["source_id"]), domain.S(args["project"]))
	case "memory-process":
		if !keys(args, "project", "limit") || !domain.ValidMemoryLimit(args["limit"]) {
			return nil, domain.ErrInvalid
		}
		return repo.ProcessMemoryJobs(ctx, domain.S(args["project"]), domain.I(args["limit"]))
	case "task-event-ingest":
		if !keys(args, "event") {
			return nil, domain.ErrInvalid
		}
		return repo.IngestTaskEvent(ctx, domain.M(args["event"]))
	case "capture-sources":
		if !keys(args, "candidate_id", "after", "limit") {
			return nil, domain.ErrInvalid
		}
		return repo.CaptureSources(ctx, domain.S(args["candidate_id"]), domain.S(args["after"]), domain.I(args["limit"]))
	case "capture-ingest":
		if !keys(args, "event") {
			return nil, domain.ErrInvalid
		}
		return repo.IngestCapture(ctx, domain.M(args["event"]))
	case "candidate-automate":
		if !keys(args, "candidate_id", "expected_head_sha256", "policy_file", "source_policy_file", "evidence_root", "receipt_sha256") {
			return nil, domain.ErrInvalid
		}
		policy, err := domain.LoadAutomationPolicy(domain.S(args["policy_file"]))
		if err != nil {
			return nil, domain.ErrInvalid
		}
		sourcePolicy, err := domain.LoadPolicy(domain.S(args["source_policy_file"]))
		if err != nil {
			return nil, domain.ErrInvalid
		}
		return repo.AutomateCandidate(ctx, r.scope.BackendID, domain.S(args["candidate_id"]), domain.S(args["expected_head_sha256"]), policy, sourcePolicy, domain.S(args["evidence_root"]), domain.S(args["receipt_sha256"]))
	case "search-observations":
		return (domain.Service{Repo: repo, Run: r.scope.RunID, Facts: r.facts}).Call(ctx, "search_observations", args)
	case "candidate-plan":
		if !keys(args, "candidate_id") {
			return nil, domain.ErrInvalid
		}
		return repo.CandidatePlan(ctx, domain.S(args["candidate_id"]))
	case "candidate-derive":
		if !keys(args, "candidate_id", "candidate_key", "necessary_conditions", "scope") {
			return nil, domain.ErrInvalid
		}
		return repo.DeriveCandidate(ctx, domain.S(args["candidate_id"]), domain.S(args["candidate_key"]), domain.M(args["necessary_conditions"]), domain.M(args["scope"]))
	case "context":
		if len(args) != 0 {
			return nil, domain.ErrInvalid
		}
		return observedContext(r.facts)
	case "state":
		if len(args) != 0 {
			return nil, domain.ErrInvalid
		}
		state, e := transfer.Fingerprint(ctx, repo.Repository, "local SQLite")
		if e != nil {
			return nil, e
		}
		count, e := repo.AvailableExperienceCount(ctx)
		if e != nil {
			return nil, e
		}
		return domain.Map{"graph_state": state, "experience_count": count, "engine": "go-sqlite"}, nil
	case "inspect":
		if !keys(args, "candidate_id") {
			return nil, domain.ErrInvalid
		}
		view, e := repo.Inspect(ctx, domain.S(args["candidate_id"]))
		if e != nil {
			return nil, e
		}
		view["next_steps"] = storage.LifecycleGuidance(domain.S(domain.M(view["head"])["state"]))
		return view, nil
	case "query":
		return (domain.Service{Repo: repo, Run: r.scope.RunID, Facts: r.facts, Proposals: r.scope.Proposals, Recall: plan}).Call(ctx, "resolve_experience", args)
	case "review":
		if !keys(args, "candidate_id", "state", "expected_head_sha256", "event_key", "reason", "principal", "expires_at", "metadata") {
			return nil, domain.ErrInvalid
		}
		grant := domain.ReviewGrant{Principal: domain.S(args["principal"]), ExpiresAt: domain.S(args["expires_at"])}
		if args["state"] == "PUBLISHED" {
			return repo.Publish(ctx, domain.S(args["candidate_id"]), domain.S(args["expected_head_sha256"]), domain.S(args["event_key"]), domain.S(args["reason"]), grant)
		}
		return repo.Transition(ctx, domain.S(args["candidate_id"]), domain.S(args["state"]), domain.S(args["expected_head_sha256"]), domain.S(args["event_key"]), domain.S(args["reason"]), grant, domain.M(args["metadata"]))
	case "source-project":
		if !keys(args, "candidate_id", "policy_file", "evidence_root", "receipt_sha256") {
			return nil, domain.ErrInvalid
		}
		policy, e := domain.LoadPolicy(domain.S(args["policy_file"]))
		if e != nil {
			return nil, domain.ErrInvalid
		}
		return repo.VerifyProjectCandidate(ctx, domain.S(args["candidate_id"]), policy, domain.S(args["evidence_root"]), domain.S(args["receipt_sha256"]))
	case "source-evaluator":
		if !keys(args, "policy_file", "evidence_root") {
			return nil, domain.ErrInvalid
		}
		return repo.AuthorizeEvaluatorSource(ctx, domain.S(args["policy_file"]), domain.S(args["evidence_root"]))
	case "feedback":
		if !keys(args, "source_id") {
			return nil, domain.ErrInvalid
		}
		return repo.FeedbackSource(ctx, domain.S(args["source_id"]))
	case "governance":
		if !keys(args, "event") {
			return nil, domain.ErrInvalid
		}
		return repo.AppendGovernance(ctx, domain.M(args["event"]))
	case "append-rule":
		if !keys(args, "experience_id", "rule", "revision") {
			return nil, domain.ErrInvalid
		}
		return repo.AppendRule(ctx, domain.S(args["experience_id"]), domain.M(args["rule"]), domain.M(args["revision"]))
	case "diagnostics":
		if len(args) != 0 {
			return nil, domain.ErrInvalid
		}
		return r.store.Diagnostics(ctx)
	case "operation-status":
		if !keys(args, "operation_id") {
			return nil, domain.ErrInvalid
		}
		return repo.OperationInfo(ctx, domain.S(args["operation_id"]))
	default:
		return nil, domain.ErrInvalid
	}
}
func (r *Runtime) backup(ctx context.Context, request engine.Request, args domain.Map, hash string) ([]byte, error) {
	if !keys(args, "destination") {
		return nil, engine.ErrInvalid
	}
	old, found, e := r.store.Read().Operation(ctx, request.ID, r.scope.RunID, hash)
	if e != nil {
		return nil, engine.ErrRecord
	}
	if found {
		return old, nil
	}
	target := domain.S(args["destination"])
	if e = r.store.Backup(ctx, target); e != nil {
		return nil, engine.ErrUnknown
	}
	pin, e := storage.FileDigest(ctx, target)
	if e != nil {
		return nil, engine.ErrUnknown
	}
	result, e := codec.Canonical(domain.Map{"status": "BACKUP_WRITTEN", "destination": target, "sha256": pin, "schema_version": storage.LogicalSchema, "verification": "RESTORE_AND_DOMAIN_VERIFICATION_REQUIRED"})
	if e != nil {
		return nil, e
	}
	if e = r.store.Write(ctx, func(repo *storage.Repository) error {
		return repo.CompleteOperation(ctx, request.ID, r.scope.RunID, hash, result)
	}); e != nil {
		return nil, engine.ErrUnknown
	}
	return result, nil
}
