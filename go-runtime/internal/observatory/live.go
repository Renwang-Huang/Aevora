package observatory

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"sort"
	"strings"
	"time"
)

type Reader struct {
	Store     *storage.Store
	Runtime   func() ([]Map, error)
	HostState func() Map
}
type pages struct {
	repo       domain.Repo
	selection  Selection
	pagination Map
}
type record struct {
	label string
	value Map
}

func (p *pages) mark(key string, ids []string, more bool, limit int) {
	var next any
	if more && len(ids) > 0 {
		after := map[string]string{}
		for k, v := range p.selection.After {
			after[k] = v
		}
		after[key] = ids[len(ids)-1]
		next = cursor(after, p.selection)
	}
	p.pagination[key] = Map{"limit": limit, "offset": p.selection.Offset, "has_more": more, "next_cursor": next, "order": "identity ASC"}
}
func (p *pages) load(ctx context.Context, headers []storage.Header) ([]record, error) {
	out := []record{}
	for _, h := range headers {
		v, e := p.repo.Required(ctx, h.Label, h.ID)
		if e != nil {
			return nil, e
		}
		out = append(out, record{h.Label, v})
	}
	return out, nil
}
func (p *pages) records(ctx context.Context, key string, labels []string, run, experience string, timeline bool, limit int) ([]record, error) {
	rows, e := p.repo.Headers(ctx, storage.PageFilter{Labels: labels, Run: run, Experience: experience, After: p.selection.After[key], Limit: limit + 1, Offset: p.selection.Offset, Timeline: timeline})
	if e != nil {
		return nil, e
	}
	more := len(rows) > limit
	if more {
		rows = rows[:limit]
	}
	ids := []string{}
	for _, h := range rows {
		ids = append(ids, h.ID)
	}
	p.mark(key, ids, more, limit)
	out, e := p.load(ctx, rows)
	if e != nil {
		return nil, e
	}
	if run != "" {
		for _, v := range out {
			if v.value["run_id"] == run {
				continue
			}
			if !timeline {
				return nil, domain.ErrConflict
			}
			c, e := p.repo.Required(ctx, "Candidate", domain.S(v.value["candidate_id"]))
			if e != nil {
				return nil, e
			}
			if c["run_id"] != run {
				return nil, domain.ErrConflict
			}
		}
	}
	return out, nil
}
func publics(rows []record) []any {
	out := []any{}
	for _, v := range rows {
		out = append(out, project(v.label, v.value))
	}
	return out
}
func (p *pages) public(ctx context.Context, key string, labels []string, run, experience string, timeline bool) ([]any, error) {
	rows, e := p.records(ctx, key, labels, run, experience, timeline, p.selection.Limit)
	if e != nil {
		return nil, e
	}
	return publics(rows), nil
}
func lifeProject(view Map) Map {
	events := []any{}
	for _, v := range domain.A(view["events"]) {
		events = append(events, project("CandidateEvent", domain.M(v)))
	}
	return Map{"candidate": project("Candidate", domain.M(view["candidate"])), "head": project("LifecycleHead", domain.M(view["head"])), "events": events, "head_sha256": view["head_sha256"], "consistency": view["consistency"]}
}
func (r Reader) Proof(ctx context.Context, candidate string) (Map, error) {
	repo := r.Store.Read()
	repo.Bounded()
	d := domain.Repo{Repository: repo}
	value, e := d.Get(ctx, "Candidate", candidate)
	if e != nil {
		return nil, e
	}
	if value == nil {
		return nil, nil
	}
	v, e := d.Inspect(ctx, candidate)
	if e != nil {
		return nil, e
	}
	plan, e := d.CandidatePlan(ctx, candidate)
	if e != nil {
		return nil, e
	}
	if v["head_sha256"] != plan["head_sha256"] {
		return nil, domain.ErrConflict
	}
	projection := lifeProject(v)
	projection["workbench"] = plan
	return Map{"mode": "LIVE", "visibility": "PUBLIC", "status": "AVAILABLE", "observed_at": time.Now().UTC().Format(time.RFC3339Nano), "candidate_id": candidate, "fallback": false, "source": Map{"core": "CandidateLifecycle.inspect", "graph": "local SQLite"}, "data": projection}, nil
}
func (p *pages) sessions(ctx context.Context, runtime []Map) ([]any, error) {
	s := p.selection
	ids, e := p.repo.Runs(ctx, s.After["sessions"], s.Offset+s.Limit+1)
	if e != nil {
		return nil, e
	}
	set := map[string]bool{}
	for _, id := range ids {
		set[id] = true
	}
	headers := map[string]Map{}
	for _, h := range runtime {
		id := domain.S(h["run_id"])
		headers[id] = h
		if id > s.After["sessions"] {
			set[id] = true
		}
	}
	ids = []string{}
	for id := range set {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	more := len(ids) > s.Offset+s.Limit
	start := min(s.Offset, len(ids))
	ids = ids[start:min(start+s.Limit, len(ids))]
	p.mark("sessions", ids, more, s.Limit)
	if s.Run != "" {
		found := false
		for _, id := range ids {
			found = found || id == s.Run
		}
		if !found {
			ids = append(ids, s.Run)
		}
	}
	out := []any{}
	for _, id := range ids {
		counts := map[string]int{}
		for _, l := range []string{"Query", "Candidate", "Decision", "VerifiedOutcome"} {
			n, e := p.repo.Count(ctx, l, id)
			if e != nil {
				return nil, e
			}
			counts[l] = n
		}
		if counts["Query"]+counts["Candidate"]+counts["Decision"]+counts["VerifiedOutcome"] == 0 && headers[id] == nil {
			continue
		}
		v := Map{"run_id": id, "session_id": nil, "status": "RECORDS_OBSERVED", "source": "ACTUAL_CORE_RECORDS", "authority": "RECORDS_ONLY; runtime identity unavailable", "process_liveness": "UNAVAILABLE_NOT_PROBED"}
		for k, value := range headers[id] {
			v[k] = value
		}
		v["query_count"], v["candidate_count"], v["decision_count"] = counts["Query"], counts["Candidate"], counts["Decision"]
		out = append(out, v)
	}
	return out, nil
}
func (p *pages) decisions(ctx context.Context) ([]any, []any, error) {
	rows, e := p.records(ctx, "queries", []string{"Query"}, p.selection.Run, p.selection.Experience, false, p.selection.Limit)
	if e != nil {
		return nil, nil, e
	}
	out := []any{}
	for _, row := range rows {
		q := row.value
		ids := domain.M(q["query_snapshot_ids"])
		if p.selection.Experience != "" {
			if _, ok := ids[p.selection.Experience]; !ok {
				return nil, nil, domain.ErrConflict
			}
		}
		sorted := []string{}
		for id := range ids {
			sorted = append(sorted, id)
		}
		sort.Strings(sorted)
		for _, id := range sorted {
			if p.selection.Experience != "" && id != p.selection.Experience {
				continue
			}
			sid := domain.S(ids[id])
			for _, edge := range []struct{ r, l, id string }{{"CONSIDERED", "Experience", id}, {"AT_SNAPSHOT", "QuerySnapshot", sid}} {
				if e = p.repo.RequireEdge(ctx, edge.r, "Query", domain.S(q["id"]), edge.l, edge.id); e != nil {
					return nil, nil, e
				}
			}
			snapshot, e := p.repo.Required(ctx, "QuerySnapshot", sid)
			if e != nil {
				return nil, nil, e
			}
			content := domain.M(snapshot["content"])
			candidate := domain.M(content["candidate"])
			if candidate["experience_id"] != id || !codec.Equal(content["context"], q["task_context"]) {
				return nil, nil, domain.ErrConflict
			}
			v := decisionView(candidate, domain.S(q["id"]), sid)
			v["run_id"], v["created_at"], v["authority"], v["as_of"] = q["run_id"], q["created_at"], "RECORDED_CORE_QUERY_SNAPSHOT", content["as_of"]
			out = append(out, v)
		}
	}
	p.pagination["decisions"] = p.pagination["queries"]
	domain.M(p.pagination["decisions"])["unit"] = "Query headers; all selected snapshots per Query"
	return out, publics(rows), nil
}
func (r Reader) Overview(ctx context.Context, s Selection) (Map, error) {
	repo := r.Store.Read()
	budget := repo.Bounded()
	p := pages{repo: domain.Repo{Repository: repo}, selection: s, pagination: Map{}}
	all := s.Resource == "overview"
	wants := func(v string) bool { return all || s.Resource == v }
	out := Map{"mode": "LIVE", "visibility": "PUBLIC", "observed_at": time.Now().UTC().Format(time.RFC3339Nano), "captured_at": nil, "archive": nil, "contract_sha256": nil, "status": "AVAILABLE"}
	if all {
		memory, e := repo.MemoryOverview(ctx, "")
		if e != nil {
			return nil, e
		}
		out["memory_loop"] = memory
	}
	if r.HostState != nil {
		out["runtime"] = r.HostState()
	}
	runtime := []Map{}
	var e error
	if wants("sessions") && r.Runtime != nil {
		runtime, e = r.Runtime()
		if e != nil {
			return nil, e
		}
	}
	sessions := []any{}
	if wants("sessions") {
		sessions, e = p.sessions(ctx, runtime)
		if e != nil {
			return nil, e
		}
	}
	experiences, available := []any{}, []any{}
	var selected Map
	if wants("experiences") {
		if s.Experience != "" {
			selected, e = p.repo.Get(ctx, "Experience", s.Experience)
			if e != nil {
				return nil, e
			}
			if selected != nil {
				experiences = append(experiences, project("Experience", selected))
			}
			p.mark("experiences", nil, false, 1)
		} else {
			experiences, e = p.public(ctx, "experiences", []string{"Experience"}, "", "", false)
			if e != nil {
				return nil, e
			}
		}
		for _, value := range experiences {
			v := domain.M(value)
			yes := true
			if candidate := domain.S(v["publication_candidate_id"]); candidate != "" {
				yes, e = p.repo.PublicationAllowed(ctx, candidate, domain.S(v["id"]))
				if e != nil {
					return nil, e
				}
			}
			if yes {
				available = append(available, v["id"])
			}
		}
	}
	candidates, heads := []any{}, []any{}
	guidance := Map{}
	if all {
		candidates, e = p.public(ctx, "candidates", []string{"Candidate"}, s.Run, "", false)
		if e != nil {
			return nil, e
		}
		for _, c := range candidates {
			id := domain.S(domain.M(c)["id"])
			sources, e := p.repo.CaptureSummary(ctx, id, domain.S(domain.M(c)["run_id"]))
			if e != nil {
				return nil, e
			}
			if sources != nil {
				domain.M(c)["capture_sources"] = sources
			}
			if strings.HasPrefix(domain.S(domain.M(c)["run_id"]), "task-episode-") {
				rows, e := repo.ExternalByKind(ctx, "", domain.S(domain.M(c)["run_id"]), domain.TaskEventKind, 1)
				if e != nil {
					return nil, e
				}
				if len(rows) > 0 {
					domain.M(c)["task_sources"] = true
				}
			}
			head, e := p.repo.Required(ctx, "LifecycleHead", "candidate-head:"+domain.H(id))
			if e != nil {
				return nil, e
			}
			if head["candidate_id"] != id {
				return nil, domain.ErrConflict
			}
			if e = p.repo.RequireEdge(ctx, "HAS_LIFECYCLE", "Candidate", id, "LifecycleHead", domain.S(head["id"])); e != nil {
				return nil, e
			}
			heads = append(heads, project("LifecycleHead", head))
			g := domain.Clone(fields.Guidance[domain.S(head["state"])])
			// The page contains public declarations; source checks are loaded
			// explicitly in the bounded candidate proof view.
			g["checklist"] = domain.CandidateChecklist(domain.M(c), domain.S(head["state"]))
			guidance[id] = g
		}
	}
	decisions, queries := []any{}, []any{}
	if wants("decisions") {
		decisions, queries, e = p.decisions(ctx)
		if e != nil {
			return nil, e
		}
	}
	recorded := []any{}
	if all {
		recorded, e = p.public(ctx, "recorded_decisions", []string{"Decision"}, s.Run, s.Experience, false)
		if e != nil {
			return nil, e
		}
		for _, v := range recorded {
			d := domain.M(v)
			if s.Experience != "" && d["experience_id"] != s.Experience {
				return nil, domain.ErrConflict
			}
		}
	}
	timeline := []any{}
	if wants("timeline") {
		timeline, e = p.public(ctx, "timeline", []string{"CandidateEvent", "GovernanceEvent", "AuditEvent", "Decision", "Query"}, s.Run, "", true)
		if e != nil {
			return nil, e
		}
	}
	trusted, external := []any{}, []any{}
	if wants("outcomes") {
		trusted, e = p.public(ctx, "trusted", []string{"VerifiedOutcome"}, s.Run, "", false)
		if e != nil {
			return nil, e
		}
		external, e = p.public(ctx, "external", []string{"ExternalObservation"}, s.Run, "", false)
		if e != nil {
			return nil, e
		}
	}
	var graph, lifecycle any
	if wants("graph") {
		graph, e = p.graph(ctx)
		if e != nil {
			return nil, e
		}
	}
	if selected != nil && domain.S(selected["publication_candidate_id"]) != "" {
		view, e := p.repo.Inspect(ctx, domain.S(selected["publication_candidate_id"]))
		if e != nil {
			return nil, e
		}
		lifecycle = lifeProject(view)
	}
	health := Map{"database": "AVAILABLE", "mcp": "UNAVAILABLE_NOT_ACTIVE_PROBED", "live_fallback": false, "backend_id": r.Store.BackendID()}
	outcomes := Map{"trusted": trusted, "external": external, "authority_policy": "Only graph VerifiedOutcome records are trusted; external observations remain unverified"}
	if all {
		totals, e := p.repo.AllCounts(ctx)
		if e != nil {
			return nil, e
		}
		totalRuns, e := p.repo.RunCount(ctx)
		if e != nil {
			return nil, e
		}
		for _, row := range runtime {
			rid := domain.S(row["run_id"])
			n := 0
			for _, label := range []string{"Query", "Candidate", "Decision", "VerifiedOutcome"} {
				c, e := p.repo.Count(ctx, label, rid)
				if e != nil {
					return nil, e
				}
				n += c
			}
			if n == 0 {
				totalRuns++
			}
		}
		summary, e := p.repo.List(ctx, "LifecycleHead", storage.Filter{Limit: s.Limit})
		if e != nil {
			return nil, e
		}
		summaryHeads := map[string]Map{}
		for _, h := range summary {
			summaryHeads[domain.S(h["id"])] = h
		}
		for _, h := range heads {
			v := domain.M(h)
			summaryHeads[domain.S(v["id"])] = v
		}
		states := Map{}
		pending := 0
		for _, h := range summaryHeads {
			state := domain.S(h["state"])
			if n, ok := states[state].(int); ok {
				states[state] = n + 1
			} else {
				states[state] = 1
			}
			if state == "PROPOSED" || state == "EVIDENCE_PENDING" || state == "ADMITTED_BOUNDED" || state == "PUBLISHING" {
				pending++
			}
		}
		records := 0
		for label, n := range totals {
			if label != "Schema" {
				records += n
			}
		}
		state, text := "EMPTY", "Database connected. This project has no records yet; connect MCP and start a task."
		summaryExperienceCount, summaryAvailable := len(experiences), len(available)
		if s.Experience != "" {
			// Keep project readiness independent of a missing selection. This
			// bounded first page never substitutes records into the selected view.
			rows, e := p.repo.List(ctx, "Experience", storage.Filter{Limit: s.Limit})
			if e != nil {
				return nil, e
			}
			summaryExperienceCount, summaryAvailable = len(rows), 0
			for _, v := range rows {
				yes := true
				if candidate := domain.S(v["publication_candidate_id"]); candidate != "" {
					yes, e = p.repo.PublicationAllowed(ctx, candidate, domain.S(v["id"]))
					if e != nil {
						return nil, e
					}
				}
				if yes {
					summaryAvailable++
				}
			}
		}
		if summaryAvailable > 0 {
			state, text = "EXPERIENCE_AVAILABLE", "Published experiences are available. Use a new task query to check applicability."
		} else if pending > 0 {
			state, text = "CANDIDATES_PENDING", "Candidates are recorded and await Host verification, review or publication."
		} else if totals["Query"] > 0 || len(sessions) > 0 {
			state, text = "ACTIVITY_RECORDED", "Task activity is recorded."
		} else if records > 0 {
			state, text = "RECORDS_PRESENT", "The project contains records."
		}
		var pendingCount, availableCount any
		if len(summaryHeads) == totals["LifecycleHead"] {
			pendingCount = pending
		}
		if summaryExperienceCount == totals["Experience"] {
			availableCount = summaryAvailable
		}
		out["project"] = Map{"graph": "local SQLite", "state": state, "summary": text, "counts": Map{"records": records, "runs": totalRuns, "queries": totals["Query"], "candidates": totals["Candidate"], "stored_experiences": totals["Experience"], "pending_candidates": pendingCount, "available_experiences": availableCount}, "count_scope": "Project aggregates; null means not fully validated in this bounded read", "loaded_counts": Map{"pending_candidates": pending, "available_experiences": summaryAvailable}, "candidate_states": states, "candidate_states_complete": len(summaryHeads) == totals["LifecycleHead"]}
		runStatus := "ALL"
		if s.Run != "" {
			runStatus = "NOT_FOUND"
			for _, v := range sessions {
				if domain.M(v)["run_id"] == s.Run {
					runStatus = "AVAILABLE"
				}
			}
		}
		experienceStatus := "ALL"
		if s.Experience != "" {
			experienceStatus = "NOT_FOUND"
			if selected != nil {
				experienceStatus = "AVAILABLE"
			}
		}
		out["selection"] = Map{"run_id": nullable(s.Run), "run_status": runStatus, "experience_id": nullable(s.Experience), "experience_status": experienceStatus}
		for k, v := range (Map{"case": nil, "sessions": sessions, "experiences": experiences, "available_experience_ids": available, "candidates": candidates, "candidate_heads": heads, "candidate_guidance": guidance, "lifecycle": lifecycle, "graph": graph, "decisions": decisions, "activity_queries": queries, "recorded_decisions": recorded, "timeline": timeline, "outcomes": outcomes, "health": health, "live_query_context": nil, "context_authority": "RECORDED_QUERY_SNAPSHOTS_ONLY; no synthetic task context", "comparison": nil, "evolution": nil, "sources": Map{"core": "Core publication gate and immutable QuerySnapshot records; no resolver execution", "graph": "local SQLite", "query_version": storage.QueryVersion}, "causal_benefit": "UNKNOWN", "agent_adoption": "UNKNOWN", "consistency": "Actual multi-query observation, not atomic snapshot", "ordering": "Pages ordered by stable identity; timestamps do not establish cross-stream causality"}) {
			out[k] = v
		}
		health["recent_core_query_records"] = totals["Query"]
		if state == "EMPTY" {
			out["status"] = "EMPTY"
		}
	} else {
		if s.Resource == "health" {
			n, e := p.repo.Count(ctx, "Query", "")
			if e != nil {
				return nil, e
			}
			health["recent_core_query_records"] = n
		}
		values := Map{"sessions": sessions, "experiences": experiences, "decisions": decisions, "timeline": timeline, "graph": graph, "outcomes": outcomes, "health": health}
		out["resource"], out["data"], out["limit"], out["offset"] = s.Resource, values[s.Resource], s.Limit, s.Offset
	}
	out["pagination"] = p.pagination
	out["read_budget"] = Map{"nodes": len(budget.Nodes), "edges": len(budget.Edges), "payload_bytes": budget.PayloadBytes, "queries": budget.Queries, "max_nodes": 500, "max_edges": 1200, "max_payload_bytes": 8 * 1024 * 1024, "max_response_bytes": 8 * 1024 * 1024}
	return out, nil
}
