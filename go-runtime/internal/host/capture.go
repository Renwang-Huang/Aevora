package host

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/capture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"path/filepath"
	"time"
)

type CaptureStatus struct {
	State        string         `json:"state"`
	Source       string         `json:"source"`
	Pending      int            `json:"pending_before_scan"`
	Invalid      int            `json:"invalid_in_scanned_batch"`
	Unauthorized int            `json:"unauthorized_in_scanned_batch"`
	Acknowledged int            `json:"acknowledged_this_epoch"`
	Observed     string         `json:"observed_at"`
	Scanned      int            `json:"files_scanned"`
	BatchLimited bool           `json:"batch_limited"`
	Cursor       string         `json:"cursor_state"`
	Callback     map[string]any `json:"callback"`
}

// captureAuthorizedLocked and the transaction using its decision share autoMu
// with route removal, so no new source is committed after a completed revoke.
func (h *Host) captureAuthorizedLocked(name string) bool {
	if h.autoPolicy == nil {
		return false
	}
	allowed := automaticProject{}
	if h.autoPolicy.Project == name {
		allowed = automaticProject{Project: name, Workspace: h.autoPolicy.Workspace}
	}
	for _, route := range h.autoPolicy.Routes {
		if route.Project == name {
			allowed = route
			break
		}
	}
	if allowed.Project == "" {
		return false
	}
	p, err := local.Load(name)
	if err != nil || p.BackendID != h.scope.BackendID || p.Workspace != allowed.Workspace {
		return false
	}
	real, err := filepath.EvalSymlinks(p.Workspace)
	return err == nil && real == p.Workspace
}

// startCapture drains only sanitized files from the owned outbox. The writer
// transaction makes source records and operation receipts atomic; a missing
// acknowledgement is reconciled using the immutable event identity.
func (h *Host) startCapture() {
	manager, ok := h.engine.(engine.Manager)
	if !ok || h.profile.Database.Kind != "sqlite" {
		return
	}
	h.wg.Add(1)
	go func() {
		defer h.wg.Done()
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()
		cursor, cursorErr := capture.ReadCursor(h.profile.Session.Root)
		acknowledged := 0
		checkCursors := map[string]string{}
		for {
			select {
			case <-h.stopContext.Done():
				return
			default:
			}
			if cursorErr != nil {
				if restored, e := capture.ReadCursor(h.profile.Session.Root); e == nil {
					cursor = restored
					cursorErr = nil
				}
			}
			scan, err := capture.ScanSince(h.profile.Session.Root, 32, cursor)
			state := "DRAINER_READY"
			cursorState := "RESTORED_OR_EMPTY"
			unauthorized := 0
			if err != nil {
				state = "OUTBOX_UNAVAILABLE"
			} else {
				if scan.Last != "" {
					cursor = scan.Last
					if cursorErr == nil {
						if e := capture.WriteCursor(h.profile.Session.Root, cursor); e != nil {
							cursorState = "WRITE_RETRY_PENDING"
							if e == capture.ErrInvalid {
								cursorErr = e
							}
						} else {
							cursorState = "PERSISTED"
						}
					}
				}
				if scan.Invalid > 0 {
					state = "INVALID_RETAINED"
				}
				for _, event := range scan.Events {
					h.autoMu.Lock()
					if !h.captureAuthorizedLocked(event.Project) {
						h.autoMu.Unlock()
						unauthorized++
						if state == "DRAINER_READY" {
							state = "PROJECT_UNAUTHORIZED"
						}
						continue
					}
					raw, _ := codec.Canonical(map[string]any{"event": event.Map()})
					ctx, cancel := context.WithTimeout(h.stopContext, 10*time.Second)
					result, e := manager.Manage(ctx, engine.Request{ID: random(), Operation: "capture-ingest", Arguments: json.RawMessage(raw), BeforeDispatch: func() error { return ctx.Err() }})
					cancel()
					h.autoMu.Unlock()
					if e != nil {
						state = "INGEST_RETRY_PENDING"
						continue
					}
					receipt, e := wire.Decode(result, wire.MaxMessage)
					pin, pe := codec.Digest(event.Map())
					if e != nil || pe != nil || receipt["event_id"] != event.ID || receipt["source_sha256"] != pin ||
						(receipt["status"] != "RECORDED_UNTRUSTED" && receipt["status"] != "ALREADY_RECORDED_UNTRUSTED") {
						state = "ACK_MISMATCH_RETAINED"
						continue
					}
					if e = capture.Acknowledge(h.profile.Session.Root, event, pin); e != nil {
						state = "ACK_RETRY_PENDING"
						continue
					}
					acknowledged++
				}
			}
			if cursorErr != nil {
				cursorState = "INVALID_RETAINED"
			}
			if cursorState == "INVALID_RETAINED" || cursorState == "WRITE_RETRY_PENDING" {
				if state == "DRAINER_READY" {
					state = "CURSOR_RECOVERY_PENDING"
				}
			}
			h.drainTaskMemory(manager)
			h.runTaskChecks(manager, checkCursors)
			callback, callbackErr := capture.ReadCallback(h.profile.Session.Root)
			if callbackErr != nil {
				callback = map[string]any{"status": "CALLBACK_STATE_UNAVAILABLE"}
			}
			h.mu.Lock()
			h.captureStatus = CaptureStatus{State: state, Source: "HOOK_EXECUTION_NOT_VERIFIED", Pending: scan.Pending, Invalid: scan.Invalid, Unauthorized: unauthorized, Acknowledged: acknowledged, Observed: time.Now().UTC().Format(time.RFC3339Nano), Scanned: scan.Scanned, BatchLimited: scan.Limited, Cursor: cursorState, Callback: callback}
			h.mu.Unlock()
			select {
			case <-h.stopContext.Done():
				return
			case <-ticker.C:
			}
		}
	}()
}
