package observatory

import (
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"io/fs"
)

//go:embed assets
var embedded embed.FS

const ReplayPin = "c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776"

var errArtifactNotPublic = errors.New("ARTIFACT_NOT_PUBLIC")

func digestBytes(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }
func asset(name string) ([]byte, error) {
	if !fs.ValidPath(name) {
		return nil, domain.ErrInvalid
	}
	return embedded.ReadFile("assets/" + name)
}
func ValidateAssets() error {
	raw, e := asset("MANIFEST.json")
	if e != nil {
		return e
	}
	var m struct {
		Pin     string `json:"replay_contract_sha256"`
		Sources map[string]struct {
			SHA string `json:"sha256"`
		} `json:"sources"`
	}
	if e = json.Unmarshal(raw, &m); e != nil {
		return e
	}
	if m.Pin != ReplayPin || len(m.Sources) < 10 || len(m.Sources) > 64 {
		return domain.ErrInvalid
	}
	for name, ref := range m.Sources {
		raw, e := asset(name)
		if e != nil {
			return e
		}
		if digestBytes(raw) != ref.SHA {
			return domain.ErrConflict
		}
	}
	_, _, e = loadReplay()
	return e
}
func loadReplay() (Map, Map, error) {
	raw, e := asset("replay/hero_scenario_contract.json")
	if e != nil {
		return nil, nil, e
	}
	if digestBytes(raw) != ReplayPin {
		return nil, nil, domain.ErrConflict
	}
	value, e := codec.Parse(raw)
	if e != nil {
		return nil, nil, e
	}
	contract := domain.M(value)
	if contract["schema_version"] != "aevora.hero/1.0" || contract["visibility"] != "PUBLIC" || contract["mode"] != "REPLAY" || contract["causal_benefit"] != "UNKNOWN" || contract["agent_adoption"] != "UNKNOWN" {
		return nil, nil, domain.ErrInvalid
	}
	refs := domain.M(contract["artifacts"])
	if len(refs) > 32 {
		return nil, nil, domain.ErrInvalid
	}
	data := Map{}
	for name, value := range refs {
		ref := domain.M(value)
		if ref["visibility"] != "PUBLIC" {
			return nil, nil, domain.ErrInvalid
		}
		raw, e := asset("replay/" + domain.S(ref["artifact_path"]))
		if e != nil {
			return nil, nil, e
		}
		if len(raw) > 8*1024*1024 || digestBytes(raw) != ref["sha256"] {
			return nil, nil, domain.ErrConflict
		}
		v, e := codec.Parse(raw)
		if e != nil {
			return nil, nil, e
		}
		data[name] = v
	}
	return contract, data, nil
}
func replayProof(name, candidate string) (Map, error) {
	c, data, e := loadReplay()
	if e != nil {
		return nil, e
	}
	if name == "contract" && candidate == "" {
		return c, nil
	}
	value, ok := data[name]
	if !ok {
		return nil, errArtifactNotPublic
	}
	if candidate != "" && (name != "lifecycle" || domain.M(domain.M(value)["candidate"])["id"] != candidate) {
		return nil, nil
	}
	return Map{"mode": "REPLAY", "visibility": "PUBLIC", "source": domain.M(c["artifacts"])[name], "data": value}, nil
}
func focus(graph Map, identity string) Map {
	all := domain.A(graph["nodes"])
	edges := domain.A(graph["edges"])
	ids := map[string]bool{}
	if identity == "" {
		for _, v := range all[:min(64, len(all))] {
			ids[domain.S(domain.M(v)["id"])] = true
		}
	} else {
		for _, v := range all {
			if domain.M(v)["id"] == identity {
				ids[identity] = true
			}
		}
		front := map[string]bool{identity: true}
		for depth := 0; depth < 3 && len(ids) < 64 && len(front) > 0; depth++ {
			found := map[string]bool{}
			for _, value := range edges {
				e := domain.M(value)
				s, t := domain.S(e["source"]), domain.S(e["target"])
				if front[s] || front[t] {
					if !ids[s] {
						found[s] = true
					}
					if !ids[t] {
						found[t] = true
					}
				}
			}
			keys := sortedKeys(found)
			front = map[string]bool{}
			for _, id := range keys[:min(len(keys), 64-len(ids))] {
				front[id] = true
				ids[id] = true
			}
		}
	}
	nodes, selected := []any{}, []any{}
	for _, v := range all {
		if ids[domain.S(domain.M(v)["id"])] {
			nodes = append(nodes, v)
		}
	}
	for _, v := range edges {
		e := domain.M(v)
		if ids[domain.S(e["source"])] && ids[domain.S(e["target"])] {
			selected = append(selected, v)
		}
	}
	status := "AVAILABLE"
	if len(nodes) < len(all) {
		status = "PARTIAL"
	}
	if len(nodes) == 0 {
		status = "EMPTY"
	}
	return Map{"nodes": nodes, "edges": selected, "status": status, "total_nodes": len(all), "total_edges": len(edges), "node_limit": 64, "disclosure": "Actual bounded subgraph, no invented nodes/edges. Layout is presentation only."}
}
func replayOverview(s Selection) (Map, error) {
	c, d, e := loadReplay()
	if e != nil {
		return nil, e
	}
	var act Map
	for _, v := range domain.A(c["acts"]) {
		if domain.M(v)["case_id"] == s.Case {
			act = domain.M(v)
		}
	}
	if act == nil {
		return nil, domain.ErrInvalid
	}
	origin, readback, pilot, life := domain.M(d["origin"]), domain.M(d["readback"]), domain.M(d["pilot"]), domain.M(d["lifecycle"])
	graph := domain.M(d["graph"])
	sessions := []any{Map{"run_id": origin["run_id"], "session_id": origin["session_id"], "status": origin["runtime_status"], "evaluation_status": "PASS", "authority": "VERIFIED_WITHIN_RECORDED_SCOPE", "started_at": origin["started_at"], "ended_at": origin["ended_at"], "native_children": origin["children"], "source_commit": origin["source_commit"]}, Map{"run_id": readback["run_id"], "session_id": readback["thread_id"], "status": readback["runtime_result"], "failure_kind": readback["failure_kind"], "evaluation_status": readback["evaluation"], "observation_status": readback["status"], "authority": "SUPPORTING"}}
	for _, side := range []string{"governance", "raw_memory"} {
		p := domain.M(pilot[side])
		sessions = append(sessions, Map{"run_id": p["run_id"], "session_id": p["session_id"], "status": "PASS", "evaluation_status": "EXTERNAL_UNVERIFIED", "authority": "EXTERNAL_UNVERIFIED", "public_tests": p["passed"]})
	}
	sessions = append(sessions, Map{"run_id": pilot["failed_attempt_run_id"], "session_id": nil, "status": "ERROR", "failure_kind": pilot["failed_attempt_status"], "authority": "EXTERNAL_UNVERIFIED", "evaluation_status": "NOT_EXECUTED"})
	decisions := []any{}
	views := domain.M(d["views"])
	for _, context := range sortedKeys(views) {
		for _, value := range domain.A(views[context]) {
			row := domain.Clone(domain.M(value))
			row["context_name"], row["authority"] = context, "AUTHORITATIVE_CORE_READ_ONLY_VIEW"
			decisions = append(decisions, row)
		}
	}
	var evolution, evolutionStage, lifecycle any
	timeline := []any{}
	if s.Case == "case-a" {
		lifecycle = life
		timeline = domain.A(life["events"])
	}
	if s.Case == "case-c" {
		ev := domain.M(d["evolution"])
		decisions = []any{}
		for _, k := range []string{"before", "after", "restored"} {
			row := domain.Clone(domain.M(ev[k]))
			row["context_name"], row["authority"] = k, "MAINTAINER_CONTROLLED_ABLATION"
			decisions = append(decisions, row)
		}
		graph = domain.M(ev["before_graph"])
		if s.Stage == "after" {
			graph = domain.M(ev["after_graph"])
		}
		evolution, evolutionStage = ev, s.Stage
		for _, value := range domain.A(domain.M(d["queries"])["queries"]) {
			q := domain.M(value)
			timeline = append(timeline, Map{"id": q["id"], "event_type": q["operation"], "created_at": q["started_at"], "cypher": q["cypher"], "line": q["line"], "line_sha256": q["line_sha256"], "authority": "MAINTAINER_CONTROLLED_ABLATION"})
		}
	}
	experiences, outcomes := []any{}, []any{}
	for _, v := range domain.A(domain.M(d["graph"])["nodes"]) {
		n := domain.M(v)
		if n["label"] == "Experience" {
			experiences = append(experiences, n["public"])
		}
		if n["label"] == "VerifiedOutcome" {
			outcomes = append(outcomes, n["public"])
		}
	}
	selected := s.Experience
	if selected == "" {
		selected = domain.S(act["experience_id"])
	}
	filtered := []any{}
	for _, v := range decisions {
		if domain.M(v)["experience_id"] == selected {
			filtered = append(filtered, v)
		}
	}
	return Map{"mode": "REPLAY", "visibility": "PUBLIC", "captured_at": c["captured_at"], "archive": c["source_archive"], "contract_sha256": ReplayPin, "status": "AVAILABLE", "case": act, "sessions": sessions, "decisions": filtered, "experiences": experiences, "graph": focus(graph, selected), "lifecycle": lifecycle, "timeline": timeline, "outcomes": Map{"trusted": outcomes, "external": pilot, "authority_policy": "External observations are never VerifiedOutcome"}, "evolution": evolution, "evolution_stage": evolutionStage, "comparison": pilot, "claims": c["claims"], "sources": c["artifacts"], "health": Map{"database": "NOT_PROBED_REPLAY", "mcp": "NOT_PROBED_REPLAY", "live_fallback": false}, "causal_benefit": "UNKNOWN", "agent_adoption": "UNKNOWN", "ordering": "Original per-source order; no inferred total cross-stream causality"}, nil
}
