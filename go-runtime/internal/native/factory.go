package native

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/legacy"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
)

// A Host shares one SQLite write pool across all authorized Runs.
func Factory() host.Factory {
	var shared *storage.Store
	var semantic *retrieval.Semantic
	var reranker *retrieval.Reranker
	return func(ctx context.Context, owner *os.File, p host.Profile, scope engine.RunContext) (engine.Engine, error) {
		if p.Database.Kind != "sqlite" {
			return legacy.New(ctx, legacy.Options{Python: os.Getenv("AEVORA_HOST_PYTHON"), Host: p.Database.Host, Port: p.Database.Port, Graph: p.Database.Graph, PasswordFile: p.Database.PasswordFile, Workers: 2}, owner, scope)
		}
		first := shared == nil
		if first {
			if p.Reranker != nil {
				var e error
				reranker, e = retrieval.NewReranker(*p.Reranker)
				if e != nil {
					return nil, e
				}
			}
			if p.Retrieval != nil {
				var e error
				semantic, e = retrieval.NewSemantic(*p.Retrieval)
				if e != nil {
					return nil, e
				}
			}
			var e error
			shared, e = storage.Open(ctx, p.Database.Path, storage.Options{Owner: owner})
			if e != nil {
				return nil, e
			}
		}
		r, e := New(ctx, shared, scope)
		if e != nil {
			if first {
				shared.Close()
				shared = nil
			}
			return nil, e
		}
		r.shared = !first
		r.semantic = semantic
		r.reranker = reranker
		return r, nil
	}
}
