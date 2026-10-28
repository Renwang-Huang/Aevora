package host

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"path/filepath"
	"sync/atomic"
)

func OfflineCall(ctx context.Context, p Profile, run, operation string, args map[string]any, manager engine.Manager) (map[string]any, error) {
	folder := filepath.Join(p.Session.Root, "s-"+random()[:16])
	if e := platform.PrivateDir(folder, true); e != nil {
		return nil, e
	}
	manifest, _ := json.Marshal(map[string]any{"schema_version": "aevora.local-session/1", "run_id": run, "events": "mcp_events.jsonl", "scope": "Trusted offline CLI operation; no consumer grant"})
	if e := platform.Exclusive(filepath.Join(folder, "session.json"), manifest); e != nil {
		return nil, e
	}
	journal, e := newJournal(filepath.Join(folder, "mcp_events.jsonl"), run)
	if e != nil {
		return nil, e
	}
	defer journal.Close()
	id := random()
	if e = journal.Event("MANAGEMENT", "offline", id, "QUEUED"); e != nil {
		return nil, e
	}
	raw, e := json.Marshal(args)
	if e != nil {
		return nil, e
	}
	var dispatched atomic.Bool
	result, e := manager.Manage(ctx, engine.Request{ID: id, Operation: operation, Arguments: raw, ValidateResult: func(raw json.RawMessage) error { return managementResultBudget(id, raw) }, BeforeDispatch: func() error {
		if ctx.Err() != nil {
			return engine.ErrNotDispatched
		}
		if e := journal.Event("MANAGEMENT", "offline", id, "DISPATCHED"); e != nil {
			return e
		}
		dispatched.Store(true)
		return nil
	}})
	state := "COMPLETED"
	if e != nil {
		state = "FAILED_KNOWN"
		if dispatched.Load() && (errors.Is(e, engine.ErrUnknown) || ctx.Err() != nil) {
			state = "UNKNOWN"
		}
	}
	if err := journal.Event("MANAGEMENT", "offline", id, state); err != nil {
		state = "UNKNOWN"
		e = engine.ErrUnknown
	}
	response := map[string]any{"status": state, "operation_id": id}
	if e != nil {
		response["code"] = safeError(e)
	} else {
		response["result"] = result
	}
	return response, nil
}
