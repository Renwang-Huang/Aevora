package native

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
)

func (r *Runtime) checkTarget(ctx context.Context) error {
	// Legacy externally-authorized tasks have no new observation fingerprint.
	// They retain their original snapshot semantics; do not invent a new pin.
	if r.facts["target_worktree_snapshot"] == nil && r.facts["target_dependency_snapshot"] == nil {
		return nil
	}
	project, err := local.Load(domain.S(r.facts["target_project"]))
	if err != nil || project.BackendID != r.scope.BackendID {
		return engine.ErrRunContext
	}
	err = local.CheckProjectFacts(r.facts, project, func(pr local.Project) (domain.Map, error) {
		base, e := observedContext(r.facts)
		if e != nil {
			return nil, e
		}
		return local.ObserveProject(ctx, pr, base)
	})
	if err != nil {
		return engine.ErrRunContext
	}
	return nil
}
