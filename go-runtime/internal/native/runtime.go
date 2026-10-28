// Package native connects the trusted Host boundary to Go domain transactions.
package native

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"sync"
)

type Runtime struct {
	store    *storage.Store
	scope    engine.RunContext
	facts    domain.Map
	binding  string
	slots    chan struct{}
	ctx      context.Context
	cancel   context.CancelFunc
	mu       sync.Mutex
	closed   bool
	calls    sync.WaitGroup
	once     sync.Once
	closeErr error
	shared   bool
	semantic *retrieval.Semantic
	reranker *retrieval.Reranker
}

func New(ctx context.Context, store *storage.Store, scope engine.RunContext) (*Runtime, error) {
	value, e := codec.Parse(scope.Facts)
	if e != nil {
		return nil, engine.ErrInvalid
	}
	facts := domain.M(value)
	if e = domain.NormalizeContext(facts, true); e != nil {
		return nil, engine.ErrInvalid
	}
	binding := domain.H(domain.Map{"backend_id": scope.BackendID, "workspace_id": scope.WorkspaceID, "run_id": scope.RunID, "facts_version": scope.FactsVersion, "facts_source": scope.FactsSource, "facts": facts})
	raw, e := codec.Canonical(facts)
	if e != nil {
		return nil, e
	}
	history, e := store.Read().List(ctx, "Query", storage.Filter{Run: scope.RunID, Limit: 4097})
	if e != nil {
		return nil, e
	}
	if len(history) > 4096 {
		return nil, engine.ErrRunContext
	}
	for _, q := range history {
		if q["context_authority"] != "TRUSTED_PINNED_PUBLIC_FACTS_ONLY" || !codec.Equal(q["pinned_public_context"], facts) {
			return nil, engine.ErrRunContext
		}
	}
	if e = store.BindRun(ctx, scope.RunID, binding, raw); e != nil {
		if errors.Is(e, storage.ErrConflict) {
			return nil, engine.ErrRunContext
		}
		return nil, e
	}
	lifetime, cancel := context.WithCancel(context.Background())
	return &Runtime{store: store, scope: scope, facts: facts, binding: binding, slots: make(chan struct{}, 1), ctx: lifetime, cancel: cancel}, nil
}

// NewConfigured is the owned offline CLI entry. Host factories share one
// adapter across Runs; this standalone entry must honor the same protected
// profile rather than silently disabling the optional retrieval lane.
func NewConfigured(ctx context.Context, store *storage.Store, scope engine.RunContext, config *retrieval.Config, rerank ...*retrieval.RerankConfig) (*Runtime, error) {
	var semantic *retrieval.Semantic
	var reranker *retrieval.Reranker
	var err error
	if len(rerank) > 1 {
		return nil, engine.ErrInvalid
	}
	if len(rerank) == 1 && rerank[0] != nil {
		reranker, err = retrieval.NewReranker(*rerank[0])
		if err != nil {
			return nil, err
		}
	}
	if config != nil {
		semantic, err = retrieval.NewSemantic(*config)
		if err != nil {
			if reranker != nil {
				reranker.Close()
			}
			return nil, err
		}
	}
	r, err := New(ctx, store, scope)
	if err != nil {
		if reranker != nil {
			reranker.Close()
		}
		if semantic != nil {
			semantic.Close()
		}
		return nil, err
	}
	r.semantic = semantic
	r.reranker = reranker
	return r, nil
}
func (r *Runtime) RunBinding() string { return r.binding }
func (r *Runtime) Health(ctx context.Context) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.closed {
		return engine.ErrUnavailable
	}
	p, e := r.store.Read().Get(ctx, "Schema", storage.LogicalSchema)
	if e == nil && p == nil {
		return engine.ErrUnavailable
	}
	return e
}
func scopeEqual(a, b engine.RunContext) bool {
	x, _ := json.Marshal(a)
	y, _ := json.Marshal(b)
	aRaw, e := codec.Normalize(x)
	if e != nil {
		return false
	}
	bRaw, e := codec.Normalize(y)
	return e == nil && string(aRaw) == string(bRaw)
}
func (r *Runtime) Call(ctx context.Context, scope engine.RunContext, request engine.Request) (json.RawMessage, error) {
	return r.execute(ctx, scope, request, false)
}
func (r *Runtime) Manage(ctx context.Context, request engine.Request) (json.RawMessage, error) {
	return r.execute(ctx, r.scope, request, true)
}
func (r *Runtime) execute(ctx context.Context, scope engine.RunContext, request engine.Request, privileged bool) (json.RawMessage, error) {
	if !scopeEqual(scope, r.scope) {
		return nil, engine.ErrInvalid
	}
	r.mu.Lock()
	if r.closed {
		r.mu.Unlock()
		return nil, engine.ErrNotDispatched
	}
	r.calls.Add(1)
	r.mu.Unlock()
	defer r.calls.Done()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	stop := context.AfterFunc(r.ctx, cancel)
	defer stop()
	select {
	case r.slots <- struct{}{}:
		defer func() { <-r.slots }()
	case <-ctx.Done():
		return nil, engine.ErrNotDispatched
	}
	if ctx.Err() != nil || request.BeforeDispatch == nil {
		return nil, engine.ErrNotDispatched
	}
	args, e := codec.Parse(request.Arguments)
	if e != nil || domain.M(args) == nil {
		return nil, engine.ErrInvalid
	}
	if e = request.BeforeDispatch(); e != nil {
		return nil, engine.ErrNotDispatched
	}
	requestHash := domain.H(domain.Map{"run_id": scope.RunID, "binding": r.binding, "operation": request.Operation, "arguments": args, "management": privileged})
	if privileged && request.Operation == "backup" {
		return r.backup(ctx, request, domain.M(args), requestHash)
	}
	// Provider I/O never holds the shared SQLite writer. Replay uses the old
	// operation result and does not invoke the provider again.
	var plan *domain.RecallPlan
	_, done, lookupErr := r.store.Read().Operation(ctx, request.ID, scope.RunID, requestHash)
	if lookupErr != nil {
		if errors.Is(lookupErr, storage.ErrConflict) {
			return nil, engine.ErrRecord
		}
		return nil, engine.ErrUnknown
	}
	if !done {
		if request.Operation == "resolve_experience" || request.Operation == "query" {
			if e = r.checkTarget(ctx); e != nil {
				return nil, e
			}
		}
		plan, e = r.prepareRecall(ctx, request.Operation, domain.M(args))
		if e != nil {
			return nil, e
		}
		if request.Operation == "resolve_experience" || request.Operation == "query" {
			if e = r.checkTarget(ctx); e != nil {
				return nil, e
			}
		}
	}
	var result []byte
	e = r.store.Write(ctx, func(repo *storage.Repository) error {
		old, found, e := repo.Operation(ctx, request.ID, scope.RunID, requestHash)
		if e != nil {
			return e
		}
		if found {
			result = old
			if request.ValidateResult != nil {
				return request.ValidateResult(result)
			}
			return nil
		}
		service := domain.Service{Repo: domain.Repo{Repository: repo}, Run: scope.RunID, Facts: r.facts, Proposals: scope.Proposals, Recall: plan}
		var value domain.Map
		if privileged {
			value, e = r.manage(ctx, domain.Repo{Repository: repo}, request.Operation, domain.M(args), plan)
		} else {
			value, e = service.Call(ctx, request.Operation, domain.M(args))
		}
		if e != nil {
			return e
		}
		result, e = codec.Canonical(value)
		if e != nil {
			return e
		}
		if len(result) > wire.MaxMessage-512 {
			return engine.ErrResultLimit
		}
		if request.ValidateResult != nil {
			if e = request.ValidateResult(result); e != nil {
				return e
			}
		}
		return repo.CompleteOperation(ctx, request.ID, scope.RunID, requestHash, result)
	})
	if e != nil {
		if errors.Is(e, engine.ErrResultLimit) {
			return nil, engine.ErrResultLimit
		}
		if errors.Is(e, storage.ErrInvalid) {
			return nil, engine.ErrInvalid
		}
		if errors.Is(e, storage.ErrConflict) {
			return nil, engine.ErrRecord
		}
		return nil, engine.ErrUnknown
	}
	return result, nil
}
func (r *Runtime) Close() error {
	r.once.Do(func() {
		r.mu.Lock()
		r.closed = true
		r.cancel()
		r.mu.Unlock()
		r.calls.Wait()
		if !r.shared {
			if r.reranker != nil {
				r.reranker.Close()
			}
			if r.semantic != nil {
				r.semantic.Close()
			}
			r.closeErr = r.store.Close()
		}
	})
	return r.closeErr
}

func (r *Runtime) Storage() *storage.Store { return r.store }
