// Package observatory projects checked records only. It has no write or resolver API.
package observatory

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"sort"
)

type Map = domain.Map

func sortedKeys[V any](m map[string]V) []string {
	keys := []string{}
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

var fields struct {
	Fields   map[string][]string `json:"console_fields"`
	Facts    []string            `json:"console_facts"`
	Guidance map[string]Map      `json:"lifecycle_guidance"`
}

func init() {
	raw, e := contracts.Files.ReadFile("reference.json")
	if e != nil {
		panic(e)
	}
	if e = json.Unmarshal(raw, &fields); e != nil {
		panic(e)
	}
	if len(fields.Fields) == 0 {
		panic("missing public Console contract")
	}
}
func project(label string, p Map) Map {
	if label == "Candidate" {
		if public, err := domain.PublicCandidate(p); err == nil {
			p = domain.Clone(p)
			for key, value := range public {
				p[key] = value
			}
		}
	}
	out := Map{}
	keys, ok := fields.Fields[label]
	if !ok {
		keys = []string{"id"}
	}
	for _, k := range keys {
		if v, ok := p[k]; ok {
			out[k] = v
		}
	}
	for _, key := range []string{"facts", "scope"} {
		if value, ok := out[key]; ok {
			clean := Map{}
			for _, k := range fields.Facts {
				if v, ok := domain.M(value)[k]; ok {
					if key == "facts" {
						if _, nested := v.(map[string]any); nested {
							continue
						}
						if _, nested := v.([]any); nested {
							continue
						}
					}
					clean[k] = v
				}
			}
			out[key] = clean
		}
	}
	return out
}
func decisionView(row Map, q, sid string) Map {
	out := Map{}
	for _, k := range []string{"experience_id", "decision", "reason", "rule_ids", "unknown_premises", "conflicting_premises", "missing_premises", "missing_material_premises", "matched_premises", "verification_steps", "retrieval_snapshot_sha256", "current_operation_coverage", "attribution", "decision_engine_version"} {
		if v, ok := row[k]; ok {
			out[k] = v
		}
	}
	out["query_id"], out["query_snapshot_id"], out["decision_id"] = q, sid, nil
	for target, source := range map[string]string{"support_paths": "principle_support_paths", "counterexample_paths": "relevant_counterexample_paths"} {
		paths := []any{}
		for _, v := range domain.A(row[source]) {
			p := domain.M(v)
			paths = append(paths, Map{"path": p["path"], "edge_types": p["edge_types"]})
		}
		out[target] = paths
	}
	return out
}
