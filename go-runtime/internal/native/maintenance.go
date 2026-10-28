package native

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"time"
)

func (r *Runtime) ReadMaintenance(ctx context.Context, operation string, args domain.Map) (domain.Map, bool, error) {
	r.mu.Lock()
	if r.closed {
		r.mu.Unlock()
		return nil, true, engine.ErrUnavailable
	}
	r.calls.Add(1)
	r.mu.Unlock()
	defer r.calls.Done()
	repo := domain.Repo{Repository: r.store.Read()}
	switch operation {
	case "memory-process":
		if !keys(args, "project", "limit") || !domain.ValidMemoryLimit(args["limit"]) {
			return nil, true, domain.ErrInvalid
		}
		rows, e := repo.Repository.ReadyMemoryJobs(ctx, domain.S(args["project"]), domain.I(args["limit"]), time.Now().UTC().Format(time.RFC3339Nano))
		if e != nil {
			return nil, true, e
		}
		if len(rows) == 0 {
			return domain.Map{"processed": 0, "results": []any{}}, true, nil
		}
		return nil, false, nil
	case "memory-state":
		if !(keys(args, "project") || keys(args, "project", "after")) {
			return nil, true, domain.ErrInvalid
		}
		v, e := repo.Repository.MemoryOverviewPage(ctx, domain.S(args["project"]), domain.S(args["after"]))
		return v, true, e
	case "inspect":
		if !keys(args, "candidate_id") {
			return nil, true, domain.ErrInvalid
		}
		v, e := repo.Inspect(ctx, domain.S(args["candidate_id"]))
		return v, true, e
	case "memory-source-info":
		if !keys(args, "source_id", "project") {
			return nil, true, domain.ErrInvalid
		}
		p, e := repo.Required(ctx, "ExternalObservation", domain.S(args["source_id"]))
		if e != nil || domain.M(p["event"])["project"] != args["project"] {
			return nil, true, domain.ErrInvalid
		}
		return domain.Map{"event": p["event"]}, true, nil
	case "memory-json-projection":
		v, e := repo.JSONCheckProjection(ctx, args, false)
		if e != nil {
			return nil, true, e
		}
		if v["status"] == "MUTATION_REQUIRED" {
			return nil, false, nil
		}
		return v, true, nil
	case "memory-check-unavailable":
		if !keys(args, "candidate_id", "project") {
			return nil, true, domain.ErrInvalid
		}
		v, e := repo.MemoryCheckUnavailable(ctx, domain.S(args["candidate_id"]), domain.S(args["project"]), false)
		if e != nil {
			return nil, true, e
		}
		if v["status"] == "MUTATION_REQUIRED" {
			return nil, false, nil
		}
		return v, true, nil
	case "memory-check-guard":
		if !keys(args, "candidate_id", "project", "basis", "record") || domain.B(args["record"]) {
			return nil, false, nil
		}
		v, e := repo.MemoryCheckProbe(ctx, domain.S(args["candidate_id"]), domain.S(args["project"]), domain.S(args["basis"]))
		if e != nil {
			return nil, true, e
		}
		if v["status"] == "MUTATION_REQUIRED" {
			return nil, false, nil
		}
		return v, true, nil
	}
	return nil, false, nil
}
