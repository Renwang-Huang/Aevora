package host

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
	"time"
)

func runSelector(root, run string) string {
	hash := sha256.Sum256([]byte(run))
	return filepath.Join(root, "runs", hex.EncodeToString(hash[:])+".json")
}
func (h *Host) Backend() engine.Engine { return h.engine }
func (h *Host) RegisterRun(ctx context.Context, run string, facts json.RawMessage, proposals bool) (map[string]any, error) {
	if h.profile.Database.Kind != "sqlite" || !validID.MatchString(run) {
		return nil, engine.ErrInvalid
	}
	if _, e := wire.Decode(facts, 16384); e != nil {
		return nil, engine.ErrInvalid
	}
	h.runMu.Lock()
	defer h.runMu.Unlock()
	h.mu.Lock()
	closed := h.closed
	old := h.runs[run]
	revoked := old != nil && old.revoked
	count := len(h.runs)
	h.mu.Unlock()
	if closed {
		return nil, engine.ErrUnavailable
	}
	p := h.profile
	p.Session.Facts = facts
	scope := Scope(p, run, proposals)
	if old != nil {
		oldFacts, e1 := codec.Normalize(old.scope.Facts)
		newFacts, e2 := codec.Normalize(facts)
		if e1 != nil || e2 != nil || string(oldFacts) != string(newFacts) || old.scope.Proposals != proposals {
			return nil, engine.ErrRunContext
		}
		if !revoked {
			return map[string]any{"status": "AUTHORIZED", "run_id": run, "session_root": p.Session.Root}, nil
		}
		old.calls.Wait()
		if e := old.engine.Close(); e != nil {
			return nil, e
		}
		if e := old.journal.Close(); e != nil {
			return nil, e
		}
	}
	if old == nil && count >= 64 {
		return nil, errors.New("AEVORA_RUN_LIMIT")
	}
	selected, e := h.factory(ctx, h.owner, p, scope)
	if e != nil {
		return nil, e
	}
	if selected == nil {
		return nil, engine.ErrUnavailable
	}
	ok := false
	defer func() {
		if !ok {
			selected.Close()
		}
	}()
	if e = selected.Health(ctx); e != nil {
		return nil, e
	}
	if e = pinRun(p, scope, selected.RunBinding()); e != nil {
		return nil, e
	}
	folder := filepath.Join(p.Session.Root, "s-"+random()[:16])
	if e = os.Mkdir(folder, 0700); e != nil {
		return nil, e
	}
	journal, e := newJournal(filepath.Join(folder, "mcp_events.jsonl"), run)
	if e != nil {
		return nil, e
	}
	defer func() {
		if !ok {
			journal.Close()
			os.Remove(filepath.Join(folder, "grant.json"))
		}
	}()
	token := random()
	manifest, _ := json.Marshal(map[string]any{"schema_version": "aevora.local-session/1", "run_id": run, "created_at": time.Now().UTC().Format(time.RFC3339Nano), "events": "mcp_events.jsonl", "scope": "Native Host; agent identity UNKNOWN"})
	if e = platform.Exclusive(filepath.Join(folder, "session.json"), manifest); e != nil {
		return nil, e
	}
	grant, _ := json.Marshal(map[string]any{"schema_version": "aevora.runtime-grant/2", "run_id": run, "token": token, "socket": platform.Address(h.folder), "server_directory": filepath.Base(h.folder)})
	if e = platform.Exclusive(filepath.Join(folder, "grant.json"), grant); e != nil {
		return nil, e
	}
	if e = journal.Event("HOST_READY", "", "", "READY"); e != nil {
		return nil, e
	}
	if e = platform.PrivateDir(filepath.Join(p.Session.Root, "runs"), true); e != nil {
		return nil, e
	}
	selector, _ := json.Marshal(map[string]any{"schema_version": "aevora.local-session/1", "run_id": run, "directory": filepath.Base(folder)})
	if e = platform.Atomic(runSelector(p.Session.Root, run), selector); e != nil {
		return nil, e
	}
	h.mu.Lock()
	if h.closed {
		h.mu.Unlock()
		return nil, engine.ErrUnavailable
	}
	authCtx, authCancel := context.WithCancel(h.stopContext)
	h.runs[run] = &authorization{scope: scope, engine: selected, token: token, folder: folder, journal: journal, ctx: authCtx, cancel: authCancel}
	h.mu.Unlock()
	ok = true
	return map[string]any{"status": "AUTHORIZED", "run_id": run, "session_root": p.Session.Root}, nil
}

// CloseRun revokes future calls and cancels in-flight calls, preserving audit.
// The initial Host Run is closed only by stopping the Host itself.
func (h *Host) CloseRun(run string) (map[string]any, error) {
	h.runMu.Lock()
	defer h.runMu.Unlock()
	h.mu.Lock()
	a := h.runs[run]
	if a == nil || run == h.scope.RunID {
		h.mu.Unlock()
		return nil, engine.ErrInvalid
	}
	if a.revoked {
		h.mu.Unlock()
		return map[string]any{"status": "REVOKED", "run_id": run, "history": "PRESERVED"}, nil
	}
	a.revoked = true
	a.cancel()
	h.mu.Unlock()
	os.Remove(filepath.Join(a.folder, "grant.json"))
	a.calls.Wait()
	if e := a.journal.Event("RUN_CLOSED", "", "", "REVOKED"); e != nil {
		return nil, e
	}
	return map[string]any{"status": "REVOKED", "run_id": run, "history": "PRESERVED"}, nil
}
func (h *Host) SessionDirectories() []string {
	h.mu.Lock()
	defer h.mu.Unlock()
	out := []string{}
	for _, a := range h.runs {
		out = append(out, a.folder)
	}
	return out
}
