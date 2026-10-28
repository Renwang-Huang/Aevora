package host

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const unregisteredWorkspace = "@unregistered-workspace"

func runtimeOnlyObservation(observation map[string]any) (map[string]any, error) {
	facts, ok := observation["facts"].(map[string]any)
	sources, sourcesOK := observation["fact_sources"].(map[string]any)
	digest, err := codec.Digest(facts)
	if !ok || !sourcesOK || err != nil || observation["source"] != "TRUSTED_NATIVE_RUNTIME_OBSERVATION" || observation["facts_sha256"] != digest {
		return nil, engine.ErrInvalid
	}
	for key := range facts {
		if strings.HasPrefix(key, "target_") {
			delete(facts, key)
			delete(sources, key)
		}
	}
	digest, err = codec.Digest(facts)
	if err != nil {
		return nil, err
	}
	observation["facts_sha256"] = digest
	observation["target_observation"] = map[string]any{"status": "UNREGISTERED_WORKSPACE", "scope": "RUNTIME_FACTS_ONLY"}
	return observation, nil
}

func sameAutomaticRoute(task local.Task, unregistered bool) bool {
	if len(task.Context) == 0 {
		return !unregistered
	}
	value, err := wire.Decode(task.Context, 65536)
	if err != nil {
		return false
	}
	target, _ := value["target_observation"].(map[string]any)
	return (target["status"] == "UNREGISTERED_WORKSPACE") == unregistered
}

type automaticProject struct {
	Project   string `json:"project"`
	Workspace string `json:"workspace"`
}

type automaticPolicy struct {
	Project   string             `json:"project"`
	Workspace string             `json:"workspace"`
	Proposals bool               `json:"proposals"`
	Routes    []automaticProject `json:"routes,omitempty"`
}

func (h *Host) configureAutomatic(args map[string]any) error {
	if !exactKeys(args, "project", "workspace", "proposals") && !exactKeys(args, "project", "workspace", "proposals", "routes") {
		return engine.ErrInvalid
	}
	if input, present := args["routes"]; present {
		routes, ok := input.([]any)
		if !ok || len(routes) > 64 {
			return engine.ErrInvalid
		}
		for _, value := range routes {
			route, ok := value.(map[string]any)
			if !ok || !exactKeys(route, "project", "workspace") {
				return engine.ErrInvalid
			}
		}
	}
	raw, _ := json.Marshal(args)
	var policy automaticPolicy
	if json.Unmarshal(raw, &policy) != nil {
		return engine.ErrInvalid
	}
	pr, err := local.Load(policy.Project)
	if err != nil || pr.BackendID != h.scope.BackendID || pr.Workspace != policy.Workspace {
		return engine.ErrInvalid
	}
	real, err := filepath.EvalSymlinks(policy.Workspace)
	if err != nil || real != policy.Workspace {
		return engine.ErrInvalid
	}
	if len(policy.Routes) > 64 {
		return engine.ErrInvalid
	}
	seen := map[string]bool{policy.Project: true}
	for _, route := range policy.Routes {
		if seen[route.Project] {
			return engine.ErrInvalid
		}
		seen[route.Project] = true
		p, e := local.Load(route.Project)
		resolved, re := filepath.EvalSymlinks(route.Workspace)
		if e != nil || p.BackendID != h.scope.BackendID || p.Workspace != route.Workspace || re != nil || resolved != route.Workspace {
			return engine.ErrInvalid
		}
	}
	sort.Slice(policy.Routes, func(i, j int) bool { return policy.Routes[i].Project < policy.Routes[j].Project })
	raw, err = json.Marshal(policy)
	if err != nil {
		return err
	}
	h.autoMu.Lock()
	defer h.autoMu.Unlock()
	if h.autoPolicy != nil {
		old := h.autoPolicy
		if old.Project != policy.Project || old.Workspace != policy.Workspace || old.Proposals != policy.Proposals {
			return errors.New("AEVORA_AUTO_POLICY_CONFLICT")
		}
		// Only the Host owner can extend this list. Existing grants cannot be
		// silently narrowed while a client still owns a Run through them.
		for _, existing := range old.Routes {
			found := false
			for _, next := range policy.Routes {
				found = found || next == existing
			}
			if !found {
				return errors.New("AEVORA_AUTO_POLICY_CONFLICT")
			}
		}
	}
	if err = platform.Atomic(filepath.Join(h.profile.Session.Root, "automatic-policy.json"), raw); err != nil {
		return err
	}
	h.autoPolicy = &policy
	if h.autoToken == "" {
		h.autoToken = random()
	}
	grant, _ := json.Marshal(map[string]any{"schema_version": "aevora.automatic-grant/1", "backend_id": h.scope.BackendID, "directory": filepath.Base(h.folder), "token": h.autoToken, "socket": platform.Address(filepath.Join(h.folder, "admin"))})
	return platform.Atomic(filepath.Join(h.profile.Session.Root, "automatic-grant.json"), grant)
}
func (h *Host) loadAutomatic() error {
	raw, err := platform.ReadPrivate(filepath.Join(h.profile.Session.Root, "automatic-policy.json"), 4096)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	args, err := wire.Decode(raw, 4096)
	if err != nil {
		return err
	}
	return h.configureAutomatic(args)
}

// automaticRoute is owner-only. Serialize it with enrollment and capture
// ingestion; no live automatic Run is interrupted and history is preserved.
func (h *Host) automaticRoute(args map[string]any) (map[string]any, error) {
	name, ok := args["project"].(string)
	apply, valid := args["apply"].(bool)
	if !exactKeys(args, "project", "apply") || !ok || !valid || !local.Name.MatchString(name) {
		return nil, engine.ErrInvalid
	}
	h.autoMu.Lock()
	defer h.autoMu.Unlock()
	if h.autoPolicy == nil || h.autoPolicy.Project == name {
		return nil, errors.New("AEVORA_ROUTE_NOT_REMOVABLE")
	}
	next := *h.autoPolicy
	next.Routes = make([]automaticProject, 0, len(h.autoPolicy.Routes))
	found := false
	remaining := []string{}
	for _, route := range h.autoPolicy.Routes {
		if route.Project == name {
			found = true
			continue
		}
		next.Routes = append(next.Routes, route)
		remaining = append(remaining, route.Project)
	}
	if !found {
		return nil, errors.New("AEVORA_ROUTE_NOT_REMOVABLE")
	}
	tasks, err := local.Tasks(name)
	if err != nil {
		return nil, err
	}
	active := []string{}
	h.mu.Lock()
	for _, item := range tasks {
		task, valid := item["task"].(local.Task)
		if !valid || !strings.HasPrefix(task.Name, "agent-") {
			continue
		}
		a := h.runs[task.Run]
		if a != nil && !a.revoked {
			active = append(active, task.Name)
		}
	}
	h.mu.Unlock()
	result := map[string]any{"status": "PREVIEW", "project": name, "active_tasks": active, "removable": len(active) == 0, "remaining_routes": remaining, "history": "PRESERVED"}
	if !apply {
		return result, nil
	}
	if len(active) != 0 {
		return nil, errors.New("AEVORA_ROUTE_IN_USE")
	}
	raw, err := json.Marshal(next)
	if err != nil {
		return nil, err
	}
	if err = platform.Atomic(filepath.Join(h.profile.Session.Root, "automatic-policy.json"), raw); err != nil {
		return nil, err
	}
	h.autoPolicy = &next
	result["status"] = "REMOVED"
	return result, nil
}

func (h *Host) automaticTask(ctx context.Context, name, project string, closeTask bool) (map[string]any, error) {
	h.autoMu.Lock()
	defer h.autoMu.Unlock()
	if h.autoPolicy == nil {
		return nil, engine.ErrInvalid
	}
	allowed := automaticProject{Project: h.autoPolicy.Project, Workspace: h.autoPolicy.Workspace}
	unregistered := project == unregisteredWorkspace
	if !unregistered && project != "" && project != allowed.Project {
		allowed = automaticProject{}
		for _, route := range h.autoPolicy.Routes {
			if route.Project == project {
				allowed = route
				break
			}
		}
	}
	if allowed.Project == "" {
		return nil, errors.New("AEVORA_PROJECT_NOT_AUTHORIZED")
	}
	pr, err := local.Load(allowed.Project)
	if err != nil || pr.BackendID != h.scope.BackendID || pr.Workspace != allowed.Workspace {
		return nil, engine.ErrInvalid
	}
	if name != "" && (len(name) != 30 || name[:6] != "agent-") {
		return nil, engine.ErrInvalid
	}
	if closeTask {
		t, _, err := local.LoadTask(pr.Name, name)
		if err != nil {
			return nil, err
		}
		if !sameAutomaticRoute(t, unregistered) {
			return nil, engine.ErrRunContext
		}
		result, err := h.CloseRun(t.Run)
		if err != nil {
			return nil, err
		}
		if err = local.SetState(t, "CLOSED", ""); err != nil {
			return nil, err
		}
		return result, nil
	}
	manager, ok := h.engine.(engine.Manager)
	if !ok {
		return nil, engine.ErrInvalid
	}
	raw, err := manager.Manage(ctx, engine.Request{ID: random(), Operation: "context", Arguments: json.RawMessage(`{}`), BeforeDispatch: func() error { return nil }})
	if err != nil {
		return nil, err
	}
	observation, err := wire.Decode(raw, wire.MaxMessage)
	if err != nil {
		return nil, err
	}
	if unregistered {
		observation, err = runtimeOnlyObservation(observation)
	} else {
		observation, err = local.ObserveProject(ctx, pr, observation)
	}
	if err != nil {
		return nil, err
	}
	raw, err = codec.Canonical(observation)
	if err != nil {
		return nil, err
	}
	facts, err := codec.Canonical(observation["facts"])
	if err != nil {
		return nil, err
	}
	var task local.Task
	if name == "" {
		name = "agent-" + random()[:24]
		task, err = local.NewObservedTask(pr, name, facts, raw, h.autoPolicy.Proposals)
	} else {
		var state local.TaskState
		task, state, err = local.LoadTask(pr.Name, name)
		if err == nil {
			old, e := codec.Normalize(task.Facts)
			if e != nil || string(old) != string(facts) || task.Proposals != h.autoPolicy.Proposals || !sameAutomaticRoute(task, unregistered) {
				return nil, engine.ErrRunContext
			}
			if state.State == "CLOSED" {
				return nil, errors.New("AEVORA_RUN_NOT_AUTHORIZED")
			}
			h.mu.Lock()
			a := h.runs[task.Run]
			revoked := a != nil && a.revoked
			h.mu.Unlock()
			if revoked {
				return nil, errors.New("AEVORA_RUN_NOT_AUTHORIZED")
			}
		}
	}
	if err != nil {
		return nil, err
	}
	if err = local.SetState(task, "AUTHORIZATION_UNKNOWN", ""); err != nil {
		return nil, err
	}
	if _, err = h.RegisterRun(ctx, task.Run, task.Facts, task.Proposals); err != nil {
		return nil, err
	}
	if err = local.SetState(task, "AUTHORIZED", ""); err != nil {
		return nil, err
	}
	scope := "REGISTERED_WORKSPACE"
	if unregistered {
		scope = "UNREGISTERED_RUNTIME_FACTS_ONLY"
	}
	return map[string]any{"run_id": task.Run, "task_name": task.Name, "status": "AUTHORIZED", "context_source": "TRUSTED_NATIVE_RUNTIME_OBSERVATION", "workspace_scope": scope}, nil
}

// The enrollment capability grants only fresh/resumed measured tasks, never
// arbitrary facts, source verification, review, database or Host credentials.
func AutomaticCall(ctx context.Context, root, name, operation string) (map[string]any, error) {
	return AutomaticProjectCall(ctx, root, name, "", operation)
}

// A selected project is only a routing hint; the Host checks its protected
// allowlist and registration and independently measures the chosen workspace.
func AutomaticProjectCall(ctx context.Context, root, name, project, operation string) (map[string]any, error) {
	raw, err := platform.ReadPrivate(filepath.Join(root, "automatic-grant.json"), 4096)
	if err != nil {
		return nil, err
	}
	grant, err := wire.Decode(raw, 4096)
	if err != nil || !exactKeys(grant, "schema_version", "backend_id", "directory", "token", "socket") || grant["schema_version"] != "aevora.automatic-grant/1" {
		return nil, wire.ErrInvalid
	}
	dir, _ := grant["directory"].(string)
	id, _ := grant["backend_id"].(string)
	token, _ := grant["token"].(string)
	socket, _ := grant["socket"].(string)
	if !directoryID.MatchString(dir) || len(id) != 64 || len(token) != 64 || socket != platform.Address(filepath.Join(root, dir, "admin")) {
		return nil, wire.ErrInvalid
	}
	if operation != "auto-open" && operation != "auto-close" {
		return nil, engine.ErrInvalid
	}
	args := map[string]any{"task_name": name}
	if project != "" {
		args["project"] = project
	}
	response, err := managementExchange(ctx, id, socket, token, "", operation, args)
	if err != nil {
		return nil, err
	}
	if response["status"] != "COMPLETED" {
		return nil, errors.New("AEVORA_AUTOMATIC_SESSION_UNAVAILABLE")
	}
	result, ok := response["result"].(map[string]any)
	if !ok {
		return nil, wire.ErrInvalid
	}
	return result, nil
}
