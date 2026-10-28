package storage

import "errors"

var ErrReadBudget = errors.New("GRAPH_READ_BUDGET_EXCEEDED")

// ReadBudget belongs to one sequential read request, including domain checks.
// Mutable heads are never cached. Every payload read is charged again.
type ReadBudget struct {
	Nodes, Edges          map[string]bool
	PayloadBytes, Queries int
}

func (r *Repository) Bounded() *ReadBudget {
	b := &ReadBudget{Nodes: map[string]bool{}, Edges: map[string]bool{}}
	r.budget = b
	return b
}
func (r *Repository) chargeQuery() error {
	if r.budget == nil {
		return nil
	}
	r.budget.Queries++
	if r.budget.Queries > 4096 {
		return ErrReadBudget
	}
	return nil
}
func (r *Repository) charge(label, id string, raw []byte) error {
	if len(raw) > 262144 {
		return ErrReadBudget
	}
	b := r.budget
	if b == nil {
		return nil
	}
	b.PayloadBytes += len(raw)
	if label == "edge" {
		b.Edges[id] = true
	} else {
		b.Nodes[label+":"+id] = true
	}
	if b.PayloadBytes > 8*1024*1024 || len(b.Nodes) > 500 || len(b.Edges) > 1200 {
		return ErrReadBudget
	}
	return nil
}
