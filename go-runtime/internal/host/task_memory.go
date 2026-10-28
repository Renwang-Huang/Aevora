package host

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/taskcapture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"path/filepath"
	"time"
)

func (h *Host) drainTaskMemory(manager engine.Manager) {
	pending, invalid, err := taskcapture.Scan(h.profile.Session.Root, 16)
	state := "READY"
	acknowledged := 0
	if err != nil {
		state = "SCAN_UNAVAILABLE"
	} else if invalid > 0 {
		state = "INVALID_RETAINED"
	}
	for _, p := range pending {
		h.autoMu.Lock()
		if !h.captureAuthorizedLocked(domain.S(p.Event["project"])) && !h.taskProjectDelegated(domain.S(p.Event["project"])) {
			h.autoMu.Unlock()
			state = "PROJECT_UNAUTHORIZED_RETAINED"
			continue
		}
		ctx, cancel := context.WithTimeout(h.stopContext, 5*time.Second)
		raw, _ := json.Marshal(domain.Map{"event": p.Event})
		result, e := manager.Manage(ctx, engine.Request{ID: random(), Operation: "task-event-ingest", Arguments: raw, BeforeDispatch: func() error { return ctx.Err() }})
		cancel()
		h.autoMu.Unlock()
		if e != nil {
			state = "INGEST_RETRY_RETAINED"
			continue
		}
		v, e := wire.Decode(result, wire.MaxMessage)
		if e != nil || v["source_id"] != domain.TaskSourceID(p.Event) || v["status"] != "RECORDED_UNTRUSTED" {
			state = "ACK_MISMATCH_RETAINED"
			continue
		}
		if e = taskcapture.Ack(p); e != nil {
			state = "ACK_RETRY_RETAINED"
			continue
		}
		acknowledged++
	}
	h.autoMu.Lock()
	if h.autoPolicy != nil {
		projects := []string{h.autoPolicy.Project}
		for _, route := range h.autoPolicy.Routes {
			projects = append(projects, route.Project)
		}
		for _, project := range projects {
			if !h.captureAuthorizedLocked(project) {
				continue
			}
			ctx, cancel := context.WithTimeout(h.stopContext, 3*time.Second)
			args, _ := json.Marshal(domain.Map{"project": project, "limit": 2})
			var e error
			handled := false
			if reader, ok := manager.(engine.MaintenanceReader); ok {
				_, handled, e = reader.ReadMaintenance(ctx, "memory-process", domain.Map{"project": project, "limit": 2})
			}
			if !handled && e == nil {
				_, e = manager.Manage(ctx, engine.Request{ID: random(), Operation: "memory-process", Arguments: args, BeforeDispatch: func() error { return ctx.Err() }})
			}
			cancel()
			if e != nil {
				state = "JOB_RETRY_PENDING"
			}
		}
	}
	h.autoMu.Unlock()
	raw, _ := json.Marshal(domain.Map{"schema_version": "aevora.task-drainer/1", "state": state, "invalid_in_batch": invalid, "acknowledged_in_batch": acknowledged, "observed_at": time.Now().UTC().Format(time.RFC3339Nano), "scope": "ONLY_AUTHORIZED_PROJECTS", "outcome": "NOT_CREATED"})
	platform.Atomic(filepath.Join(h.profile.Session.Root, "task-drainer.json"), raw)
}
