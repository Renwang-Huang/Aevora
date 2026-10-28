package host

import (
	"context"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"net"
	"path/filepath"
	"sync/atomic"
	"time"
)

func (h *Host) startManagement() error {
	folder := filepath.Join(h.folder, "admin")
	if e := platform.PrivateDir(folder, true); e != nil {
		return e
	}
	listener, e := platform.Listen(platform.Address(folder))
	if e != nil {
		return e
	}
	h.management = listener
	h.managementToken = random()
	h.managementNonces = map[string]bool{}
	raw, _ := json.Marshal(map[string]any{"schema_version": "aevora.management-grant/1", "backend_id": h.scope.BackendID, "directory": filepath.Base(h.folder), "token": h.managementToken, "socket": platform.Address(folder)})
	if e = platform.Atomic(filepath.Join(RegistryDir(h.scope.BackendID), "management.json"), raw); e != nil {
		return e
	}
	h.managementPublished = true
	h.wg.Add(1)
	go func() {
		defer h.wg.Done()
		slots := make(chan struct{}, 2)
		for {
			c, e := listener.Accept()
			if e != nil {
				return
			}
			h.mu.Lock()
			if h.closed {
				h.mu.Unlock()
				c.Close()
				continue
			}
			select {
			case slots <- struct{}{}:
				h.wg.Add(1)
				go func() { defer h.wg.Done(); defer func() { <-slots }(); h.managementConnection(c) }()
			default:
				c.Close()
			}
			h.mu.Unlock()
		}
	}()
	return nil
}
func (h *Host) managementConnection(c net.Conn) {
	defer c.Close()
	if !platform.SameUser(c, true) {
		return
	}
	session := "management-" + random()[:16]
	h.mu.Lock()
	if h.closed {
		h.mu.Unlock()
		return
	}
	h.sessions[session] = c
	h.mu.Unlock()
	defer func() { h.mu.Lock(); delete(h.sessions, session); h.mu.Unlock() }()
	c.SetDeadline(time.Now().Add(10 * time.Second))
	raw, e := wire.ReadPacketLimit(c, 4096)
	if e != nil || len(raw) > 4096 {
		return
	}
	auth, e := wire.Decode(raw, 4096)
	if e != nil || !exactKeys(auth, "schema_version", "backend_id", "token", "nonce") || auth["schema_version"] != "aevora.management-auth/1" || auth["backend_id"] != h.scope.BackendID {
		return
	}
	token, _ := auth["token"].(string)
	nonce, _ := auth["nonce"].(string)
	h.autoMu.Lock()
	automatic := len(h.autoToken) == 64 && subtle.ConstantTimeCompare([]byte(token), []byte(h.autoToken)) == 1
	h.autoMu.Unlock()
	if len(token) != 64 || len(nonce) != 64 || (!automatic && subtle.ConstantTimeCompare([]byte(token), []byte(h.managementToken)) != 1) {
		return
	}
	if _, e = hex.DecodeString(nonce); e != nil {
		return
	}
	h.mu.Lock()
	replay := h.managementNonces[nonce] || len(h.managementNonces) >= 1024
	if !replay {
		h.managementNonces[nonce] = true
	}
	h.mu.Unlock()
	if replay {
		return
	}
	if e = wire.WritePacket(c, map[string]any{"status": "READY"}); e != nil {
		return
	}
	raw, e = wire.ReadPacket(c)
	if e != nil {
		return
	}
	request, e := wire.Decode(raw, wire.MaxMessage)
	if e != nil || !exactKeys(request, "schema_version", "run_id", "operation", "arguments") || request["schema_version"] != "aevora.management-request/1" {
		return
	}
	operation, _ := request["operation"].(string)
	args, ok := request["arguments"].(map[string]any)
	run, _ := request["run_id"].(string)
	if !ok {
		return
	}
	_, nameValid := args["task_name"].(string)
	project, projectValid := args["project"].(string)
	validAutomaticArgs := exactKeys(args, "task_name") || (exactKeys(args, "task_name", "project") && projectValid && project != "")
	if automatic && (operation != "auto-open" && operation != "auto-close" || !validAutomaticArgs || !nameValid || run != "") {
		wire.WritePacket(c, map[string]any{"status": "FAILED_KNOWN", "code": "AEVORA_INVALID_OR_UNAUTHORIZED_INPUT"})
		return
	}
	if run == "" {
		run = h.scope.RunID
	}
	h.mu.Lock()
	a := h.runs[run]
	revoked := a != nil && a.revoked
	if h.closed {
		h.mu.Unlock()
		return
	}
	h.operations.Add(1)
	h.mu.Unlock()
	defer h.operations.Done()
	if (a == nil || revoked) && operation != "open-run" && operation != "close-run" {
		wire.WritePacket(c, map[string]any{"status": "FAILED_KNOWN", "code": "AEVORA_RUN_NOT_AUTHORIZED"})
		return
	}
	journal := h.journal
	id := random()
	if e = journal.Event("MANAGEMENT", session, id, "QUEUED"); e != nil {
		return
	}
	if e = wire.WritePacket(c, map[string]any{"status": "QUEUED", "operation_id": id}); e != nil {
		journal.Event("MANAGEMENT", session, id, "FAILED_KNOWN")
		return
	}
	c.SetDeadline(time.Now().Add(65 * time.Second))
	ctx, cancel := context.WithTimeout(h.stopContext, 60*time.Second)
	defer cancel()
	if a != nil && operation != "open-run" && operation != "close-run" {
		h.mu.Lock()
		if a.revoked {
			h.mu.Unlock()
			return
		}
		a.calls.Add(1)
		h.mu.Unlock()
		defer a.calls.Done()
		if a.ctx != nil {
			stopRun := context.AfterFunc(a.ctx, cancel)
			defer stopRun()
		}
	}
	var dispatched atomic.Bool
	before := func() error {
		if ctx.Err() != nil {
			return engine.ErrNotDispatched
		}
		if e := journal.Event("MANAGEMENT", session, id, "DISPATCHED"); e != nil {
			return e
		}
		dispatched.Store(true)
		return nil
	}
	var result json.RawMessage
	if operation == "configure-automatic" {
		if e = before(); e == nil {
			e = h.configureAutomatic(args)
			if e == nil {
				result = json.RawMessage(`{"status":"AUTOMATIC_SESSIONS_CONFIGURED"}`)
			}
		}
	} else if operation == "automatic-route" {
		if e = before(); e == nil {
			var value map[string]any
			value, e = h.automaticRoute(args)
			if e == nil {
				result, e = json.Marshal(value)
			}
		}
	} else if automatic {
		if e = before(); e == nil {
			var value map[string]any
			value, e = h.automaticTask(ctx, args["task_name"].(string), project, operation == "auto-close")
			if e == nil {
				result, e = json.Marshal(value)
			}
		}
	} else if operation == "open-run" {
		if !exactKeys(args, "public_context", "enable_proposals") {
			e = engine.ErrInvalid
		} else {
			facts, _ := json.Marshal(args["public_context"])
			proposals, valid := args["enable_proposals"].(bool)
			if !valid {
				e = engine.ErrInvalid
			} else if e = before(); e == nil {
				var value map[string]any
				value, e = h.RegisterRun(ctx, run, facts, proposals)
				if e == nil {
					result, e = json.Marshal(value)
				}
			}
		}
	} else if operation == "close-run" {
		if len(args) != 0 {
			e = engine.ErrInvalid
		} else if e = before(); e == nil {
			var value map[string]any
			value, e = h.CloseRun(run)
			if e == nil {
				result, e = json.Marshal(value)
			}
		}
	} else if manager, ok := a.engine.(engine.Manager); ok {
		arguments, _ := json.Marshal(args)
		result, e = manager.Manage(ctx, engine.Request{ID: id, Operation: operation, Arguments: arguments, BeforeDispatch: before, ValidateResult: func(raw json.RawMessage) error { return managementResultBudget(id, raw) }})
	} else {
		e = engine.ErrInvalid
	}
	state := "COMPLETED"
	if e != nil {
		state = "FAILED_KNOWN"
		if dispatched.Load() && (errors.Is(e, engine.ErrUnknown) || ctx.Err() != nil) {
			state = "UNKNOWN"
		}
	}
	if err := journal.Event("MANAGEMENT", session, id, state); err != nil {
		state = "UNKNOWN"
		e = engine.ErrUnknown
	}
	response := map[string]any{"status": state, "operation_id": id}
	if e != nil {
		response["code"] = safeError(e)
	} else {
		response["result"] = result
	}
	if e = wire.WritePacket(c, response); e == nil {
		journal.Event("MANAGEMENT_RESPONSE", session, id, "WRITTEN_TO_TRANSPORT")
	}
}

// ManagementCall never retries a dispatched request. A queued acknowledgement
// preserves the operation identity if the connection ends before its result.
func ManagementCall(ctx context.Context, p Profile, run, operation string, args map[string]any) (map[string]any, error) {
	id := BackendID(p)
	raw, e := platform.ReadPrivate(filepath.Join(RegistryDir(id), "management.json"), 4096)
	if e != nil {
		return nil, errors.New("AEVORA_HOST_UNAVAILABLE")
	}
	grant, e := wire.Decode(raw, 4096)
	if e != nil || !exactKeys(grant, "schema_version", "backend_id", "directory", "token", "socket") || grant["schema_version"] != "aevora.management-grant/1" || grant["backend_id"] != id {
		return nil, wire.ErrInvalid
	}
	directory, _ := grant["directory"].(string)
	socket, _ := grant["socket"].(string)
	token, _ := grant["token"].(string)
	if !directoryID.MatchString(directory) || len(token) != 64 || socket != platform.Address(filepath.Join(p.Session.Root, directory, "admin")) {
		return nil, wire.ErrInvalid
	}
	return managementExchange(ctx, id, socket, token, run, operation, args)
}
func managementExchange(ctx context.Context, id, socket, token, run, operation string, args map[string]any) (map[string]any, error) {
	var raw []byte
	c, e := platform.Dial(ctx, socket)
	if e != nil {
		return nil, errors.New("AEVORA_HOST_UNAVAILABLE")
	}
	defer c.Close()
	stop := context.AfterFunc(ctx, func() { c.Close() })
	defer stop()
	if !platform.SameUser(c, false) {
		return nil, platform.ErrUnsafe
	}
	c.SetDeadline(time.Now().Add(10 * time.Second))
	if e = wire.WritePacket(c, map[string]any{"schema_version": "aevora.management-auth/1", "backend_id": id, "token": token, "nonce": random()}); e != nil {
		return nil, e
	}
	raw, e = wire.ReadPacket(c)
	if e != nil {
		return nil, e
	}
	ready, e := wire.Decode(raw, 4096)
	if e != nil || ready["status"] != "READY" {
		return nil, engine.ErrInvalid
	}
	if e = wire.WritePacket(c, map[string]any{"schema_version": "aevora.management-request/1", "run_id": run, "operation": operation, "arguments": args}); e != nil {
		return nil, e
	}
	raw, e = wire.ReadPacket(c)
	if e != nil {
		return nil, e
	}
	queued, e := wire.Decode(raw, 4096)
	if e != nil {
		return nil, e
	}
	if queued["status"] != "QUEUED" {
		return queued, nil
	}
	opid, _ := queued["operation_id"].(string)
	c.SetDeadline(time.Now().Add(65 * time.Second))
	raw, e = wire.ReadPacket(c)
	if e != nil {
		return map[string]any{"status": "UNKNOWN", "operation_id": opid, "code": engine.ErrUnknown.Error()}, nil
	}
	response, e := wire.Decode(raw, wire.MaxMessage)
	if e != nil {
		return nil, e
	}
	if response["operation_id"] != opid {
		return nil, wire.ErrInvalid
	}
	return response, nil
}
