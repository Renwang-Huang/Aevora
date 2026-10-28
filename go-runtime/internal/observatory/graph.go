package observatory

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
)

func (p *pages) graph(ctx context.Context) (Map, error) {
	s := p.selection
	headers := []storage.Header{}
	ids := []string{}
	truncated := false
	var total any
	scope := "PROJECT_PAGE"
	if s.Experience != "" {
		scope = "EXPERIENCE_NEIGHBORHOOD"
		v, e := p.repo.Get(ctx, "Experience", s.Experience)
		if e != nil {
			return nil, e
		}
		if v != nil {
			headers = append(headers, storage.Header{Label: "Experience", ID: s.Experience})
			ids = append(ids, s.Experience)
		}
		front := append([]string{}, ids...)
		relations := []string{"HAS_REVISION", "USES_RULE", "REQUIRES", "SUPPORTED_BY", "COUNTEREXAMPLE", "OBSERVED_OUTCOME", "VERIFIES", "IN_CONTEXT", "FOR_TASK", "PUBLISHED_FROM", "HAS_LIFECYCLE", "HAS_CANDIDATE_EVENT"}
		for depth := 0; depth < 3 && len(front) > 0 && len(ids) < 64; depth++ {
			room := 64 - len(ids)
			rows, e := p.repo.Neighbors(ctx, front, ids, "", relations, room+1)
			if e != nil {
				return nil, e
			}
			if len(rows) > room {
				truncated = true
				rows = rows[:room]
			}
			front = []string{}
			for _, h := range rows {
				headers = append(headers, h)
				ids = append(ids, h.ID)
				front = append(front, h.ID)
			}
		}
		if len(front) > 0 {
			rows, e := p.repo.Neighbors(ctx, front, ids, "", nil, 1)
			if e != nil {
				return nil, e
			}
			truncated = truncated || len(rows) > 0
		}
		p.pagination["graph"] = Map{"limit": 64, "has_more": truncated, "next_cursor": nil, "order": "bounded breadth first, identity ASC", "depth": 3}
	} else {
		limit := min(s.Limit, 64)
		rows, e := p.repo.Headers(ctx, storage.PageFilter{Run: s.Run, After: s.After["graph"], Limit: limit + 1, Offset: s.Offset})
		if e != nil {
			return nil, e
		}
		more := len(rows) > limit
		if more {
			rows = rows[:limit]
		}
		headers = rows
		for _, h := range rows {
			ids = append(ids, h.ID)
		}
		p.mark("graph", ids, more, limit)
		truncated = more || s.Offset > 0 || s.After["graph"] != ""
		counts, e := p.repo.AllCounts(ctx)
		if e != nil {
			return nil, e
		}
		n := 0
		for label, count := range counts {
			if label != "Schema" {
				n += count
			}
		}
		total = n
		if s.Run != "" {
			scope = "RUN_NEIGHBORHOOD"
			n = 0
			for label := range counts {
				v, e := p.repo.Count(ctx, label, s.Run)
				if e != nil {
					return nil, e
				}
				n += v
			}
			page := domain.M(p.pagination["graph"])
			page["total_seed_nodes"], page["depth"] = n, 1
			total = nil
			room := 64 - len(ids)
			neighbors, e := p.repo.Neighbors(ctx, ids, ids, s.Run, nil, room+1)
			if e != nil {
				return nil, e
			}
			if len(neighbors) > room {
				truncated = true
				neighbors = neighbors[:room]
			}
			for _, h := range neighbors {
				ids = append(ids, h.ID)
				headers = append(headers, h)
			}
		}
	}
	rows, e := p.load(ctx, headers)
	if e != nil {
		return nil, e
	}
	nodes := []any{}
	for _, v := range rows {
		if s.Run != "" && s.Experience == "" {
			if run, exists := v.value["run_id"]; exists && run != s.Run {
				return nil, domain.ErrConflict
			}
		}
		nodes = append(nodes, Map{"id": v.value["id"], "label": v.label, "public": project(v.label, v.value), "stored_payload_sha256": domain.H(v.value)})
	}
	edges, e := p.repo.Induced(ctx, ids, 1200)
	if e != nil {
		return nil, e
	}
	publicEdges := []any{}
	for _, v := range edges {
		publicEdges = append(publicEdges, Map{"source": v.SourceID, "relation": v.Relation, "id": v.ID, "stored_payload_sha256": v.SHA256, "target": v.TargetID})
	}
	status := "AVAILABLE"
	if truncated {
		status = "PARTIAL"
	} else if len(nodes) == 0 {
		status = "EMPTY"
	}
	return Map{"nodes": nodes, "edges": publicEdges, "status": status, "total_nodes": total, "total_edges": nil, "node_limit": 64, "scope": scope, "disclosure": "Actual bounded local read; omitted nodes and edges are not inferred."}, nil
}
