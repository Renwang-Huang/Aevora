package transfer

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"sort"
)

func Fingerprint(ctx context.Context, r *storage.Repository, graphName string) (Map, error) {
	nodes, edges := []any{}, []any{}
	e := r.WalkRaw(ctx, func(l, id string, raw []byte, sha string) error {
		if len(nodes) >= 100000 {
			return storage.ErrReadBudget
		}
		nodes = append(nodes, []any{[]any{l}, id, sha})
		return nil
	}, func(v storage.Edge, raw []byte) error {
		if len(edges) >= 200000 {
			return storage.ErrReadBudget
		}
		edges = append(edges, []any{v.SourceID, v.Relation, v.ID, v.SHA256, v.TargetID})
		return nil
	})
	if e != nil {
		return nil, e
	}
	sort.Slice(edges, func(i, j int) bool {
		a, b := domain.A(edges[i]), domain.A(edges[j])
		for _, index := range []int{0, 1, 2, 4} {
			if a[index] != b[index] {
				return domain.S(a[index]) < domain.S(b[index])
			}
		}
		return false
	})
	return Map{"graph_name": graphName, "node_count": len(nodes), "edge_count": len(edges), "graph_sha256": domain.H(Map{"nodes": nodes, "edges": edges}), "query_version": storage.QueryVersion}, nil
}
