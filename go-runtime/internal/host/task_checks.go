package host

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/jsoncheck"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/taskcapture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"path/filepath"
	"time"
)

func (h *Host) checkBindingValid(b taskcapture.CheckBinding) bool {
	p, e := local.Load(b.Project)
	return e == nil && p.BackendID == h.scope.BackendID && p.Workspace == b.Workspace
}
func (h *Host) taskProjectDelegated(name string) bool {
	bindings, _ := taskcapture.InstalledChecks(h.profile.Session.Root, h.scope.BackendID)
	for _, b := range bindings {
		if b.Project == name && h.checkBindingValid(b) {
			return true
		}
	}
	return false
}

// This actor uses the internal trusted manager. It does not consume external
// control-plane authentication nonces or acquire any model/Agent capability.
func (h *Host) runTaskChecks(manager engine.Manager, cursors map[string]string) {
	bindings, invalid := taskcapture.InstalledChecks(h.profile.Session.Root, h.scope.BackendID)
	results := []any{}
	activeKeys := map[string]bool{"__plan_rotation": true}
	start := 0
	for i, b := range bindings {
		if b.Project > cursors["__plan_rotation"] {
			start = i
			break
		}
	}
	for index := 0; index < len(bindings) && index < 2; index++ {
		b := bindings[(start+index)%len(bindings)]
		cursors["__plan_rotation"] = b.Project
		if !h.checkBindingValid(b) {
			continue
		}
		p, e := jsoncheck.Load(b.PlanFile)
		if e != nil || !b.PlanValid {
			p = jsoncheck.Plan{Project: b.Project, TaskRef: b.TaskRef, Unavailable: true}
		}
		p.Workspace = b.Workspace
		p.PlanPath = b.PlanFile
		ctx, cancel := context.WithTimeout(h.stopContext, time.Second)
		invoke := func(ctx context.Context, op string, args domain.Map) (domain.Map, error) {
			if reader, ok := manager.(engine.MaintenanceReader); ok {
				result, handled, e := reader.ReadMaintenance(ctx, op, args)
				if handled || e != nil {
					return result, e
				}
			}
			raw, e := json.Marshal(args)
			if e != nil {
				return nil, e
			}
			out, e := manager.Manage(ctx, engine.Request{ID: random(), Operation: op, Arguments: raw, BeforeDispatch: func() error { return ctx.Err() }})
			if e != nil {
				return nil, e
			}
			return wire.Decode(out, wire.MaxMessage)
		}
		key := b.Project + ":" + b.PlanSHA
		activeKeys[key] = true
		result, e := jsoncheck.Sweep(ctx, p, cursors[key], invoke)
		cancel()
		if e != nil {
			results = append(results, domain.Map{"project": b.Project, "state": "CHECK_FAILED_RETAINED"})
			continue
		}
		cursors[key] = domain.S(result["next_cursor"])
		states := []any{}
		for _, value := range domain.A(result["results"]) {
			v := domain.M(value)
			states = append(states, domain.Map{"status": v["status"], "candidate_id": v["candidate_id"]})
		}
		results = append(results, domain.Map{"project": b.Project, "state": "SCANNING", "results": states})
	}
	for key := range cursors {
		if !activeKeys[key] {
			delete(cursors, key)
		}
	}
	raw, _ := json.Marshal(domain.Map{"schema_version": "aevora.task-check-status/1", "projects": results, "invalid_bindings": invalid, "observed_at": time.Now().UTC().Format(time.RFC3339Nano), "authority": "LOCAL_STANDING_POLICY_ACTOR; NO_ADOPTION_OR_CAUSAL_CLAIM"})
	platform.Atomic(filepath.Join(h.profile.Session.Root, "task-check-status.json"), raw)
}
