package host

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/buildinfo"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
	"log/slog"
	"net"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"
)

type Factory func(context.Context, *os.File, Profile, engine.RunContext) (engine.Engine, error)
type authorization struct {
	scope         engine.RunContext
	engine        engine.Engine
	token, folder string
	journal       *Journal
	ctx           context.Context
	cancel        context.CancelFunc
	revoked       bool
	calls         sync.WaitGroup
}
type Host struct {
	mu                       sync.Mutex
	profile                  Profile
	scope                    engine.RunContext
	owner                    *os.File
	engine                   engine.Engine
	listener                 net.Listener
	folder, token            string
	journal                  *Journal
	frames                   int
	nonces                   map[string]bool
	sessions                 map[string]net.Conn
	slots                    chan struct{}
	wg                       sync.WaitGroup
	operations               sync.WaitGroup
	stopContext              context.Context
	stopCancel               context.CancelFunc
	closed                   bool
	closeOnce                sync.Once
	closeErr                 error
	factory                  Factory
	runMu                    sync.Mutex
	runs                     map[string]*authorization
	management               net.Listener
	managementToken          string
	managementPublished      bool
	managementNonces         map[string]bool
	autoMu                   sync.Mutex
	autoPolicy               *automaticPolicy
	autoToken                string
	runtimeState, consoleURL string
	toolCalls                int
	statusErr                error
	captureStatus            CaptureStatus
}

func random() string {
	var v [32]byte
	if _, e := rand.Read(v[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(v[:])
}

func New(ctx context.Context, p Profile, run string, proposals bool, f Factory) (h *Host, err error) {
	if run == "" {
		run = "local-" + random()[:24]
	}
	if !validID.MatchString(run) {
		return nil, engine.ErrInvalid
	}
	if err = platform.PrivateDir(p.Session.Root, true); err != nil {
		return nil, err
	}
	h = &Host{profile: p, scope: Scope(p, run, proposals), nonces: map[string]bool{}, sessions: map[string]net.Conn{}, slots: make(chan struct{}, 4)}
	h.stopContext, h.stopCancel = context.WithCancel(ctx)
	h.owner, err = Own(p)
	if err != nil {
		h.stopCancel()
		return nil, err
	}
	cleanup := h
	defer func() {
		if err != nil {
			cleanup.Close()
		}
	}()
	selected, e := f(ctx, h.owner, p, h.scope)
	if e != nil {
		return nil, e
	}
	if selected == nil {
		return nil, engine.ErrUnavailable
	}
	h.engine = selected
	if err = h.engine.Health(ctx); err != nil {
		return nil, err
	}
	if err = pinRun(p, h.scope, h.engine.RunBinding()); err != nil {
		return nil, err
	}
	h.folder = filepath.Join(p.Session.Root, "s-"+random()[:16])
	if err = os.Mkdir(h.folder, 0700); err != nil {
		return nil, err
	}
	path := platform.Address(h.folder)
	h.journal, err = newJournal(filepath.Join(h.folder, "mcp_events.jsonl"), run)
	if err != nil {
		return nil, err
	}
	h.listener, err = platform.Listen(path)
	if err != nil {
		return nil, err
	}
	h.token = random()
	for name, v := range map[string]any{
		"session.json": map[string]any{"schema_version": "aevora.local-session/1", "run_id": run, "created_at": time.Now().UTC().Format(time.RFC3339Nano), "events": "mcp_events.jsonl", "scope": "Native Host; agent identity UNKNOWN"},
		"grant.json":   map[string]any{"schema_version": "aevora.runtime-grant/1", "run_id": run, "token": h.token, "socket": path},
	} {
		raw, _ := json.Marshal(v)
		if err = platform.Exclusive(filepath.Join(h.folder, name), raw); err != nil {
			return nil, err
		}
	}
	if err = h.journal.Event("HOST_READY", "", "", "READY"); err != nil {
		return nil, err
	}
	selector, _ := json.Marshal(map[string]any{"schema_version": "aevora.local-session/1", "directory": filepath.Base(h.folder), "run_id": run})
	if err = platform.Atomic(filepath.Join(p.Session.Root, "current.json"), selector); err != nil {
		return nil, err
	}
	h.factory = f
	authCtx, authCancel := context.WithCancel(h.stopContext)
	h.runs = map[string]*authorization{run: {scope: h.scope, engine: h.engine, token: h.token, folder: h.folder, journal: h.journal, ctx: authCtx, cancel: authCancel}}
	if p.Database.Kind == "sqlite" {
		if err = platform.PrivateDir(filepath.Join(p.Session.Root, "runs"), true); err != nil {
			return nil, err
		}
		if err = platform.Atomic(runSelector(p.Session.Root, run), selector); err != nil {
			return nil, err
		}
		if err = h.startManagement(); err != nil {
			return nil, err
		}
		if err = h.loadAutomatic(); err != nil {
			return nil, err
		}
	}
	if e := h.startStatus(); e != nil {
		return nil, e
	}
	h.startCapture()
	return h, nil
}

func (h *Host) Folder() string { return h.folder }
func (h *Host) RunID() string  { return h.scope.RunID }
func (h *Host) Serve(ctx context.Context) error {
	go func() {
		select {
		case <-ctx.Done():
			h.stopConnections()
		case <-h.stopContext.Done():
		}
	}()
	for {
		c, e := h.listener.Accept()
		if e != nil {
			h.mu.Lock()
			closed := h.closed
			h.mu.Unlock()
			if ctx.Err() != nil || closed {
				return nil
			}
			return e
		}
		h.mu.Lock()
		if h.closed {
			h.mu.Unlock()
			c.Close()
			return nil
		}
		select {
		case h.slots <- struct{}{}:
			h.wg.Add(1)
			go func() { defer h.wg.Done(); defer func() { <-h.slots }(); h.connection(ctx, c) }()
		default:
			c.Close()
		}
		h.mu.Unlock()
	}
}

func (h *Host) stopConnections() {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.closed = true
	if h.stopCancel != nil {
		h.stopCancel()
	}
	if h.listener != nil {
		h.listener.Close()
	}
	if h.management != nil {
		h.management.Close()
	}
	for _, c := range h.sessions {
		c.Close()
	}
}
func (h *Host) Revoke(id string) bool {
	h.mu.Lock()
	defer h.mu.Unlock()
	c, ok := h.sessions[id]
	if ok {
		c.Close()
	}
	return ok
}

func (h *Host) Close() error {
	h.closeOnce.Do(func() {
		h.stopConnections()
		h.wg.Wait()
		h.runMu.Lock()
		if h.engine != nil {
			h.closeErr = h.engine.Close()
		}
		for _, a := range h.runs {
			if a.engine != h.engine {
				h.closeErr = errors.Join(h.closeErr, a.engine.Close())
			}
		}
		h.runMu.Unlock()
		h.operations.Wait()
		if h.journal != nil {
			if e := h.journal.Event("HOST_CLOSED", "", "", "REVOKED"); e != nil {
				h.closeErr = e
			}
			if e := h.journal.Close(); e != nil {
				h.closeErr = e
			}
		}
		if h.folder != "" {
			os.Remove(filepath.Join(h.folder, "grant.json"))
			os.Remove(filepath.Join(h.folder, "mcp.sock"))
		}
		for _, a := range h.runs {
			if a.journal != h.journal {
				a.journal.Event("HOST_CLOSED", "", "", "REVOKED")
				a.journal.Close()
			}
			os.Remove(filepath.Join(a.folder, "grant.json"))
		}
		if h.managementPublished {
			os.Remove(filepath.Join(RegistryDir(h.scope.BackendID), "management.json"))
		}
		if h.autoPolicy != nil {
			os.Remove(filepath.Join(h.profile.Session.Root, "automatic-grant.json"))
		}
		if h.owner != nil {
			h.mu.Lock()
			h.runtimeState = "STOPPED"
			h.mu.Unlock()
			if e := h.publishStatus(); e != nil {
				h.closeErr = errors.Join(h.closeErr, e)
			}
			h.closeErr = errors.Join(h.closeErr, h.statusErr)
			if e := h.owner.Close(); e != nil {
				h.closeErr = e
			}
		}
	})
	return h.closeErr
}

func (h *Host) connection(ctx context.Context, c net.Conn) {
	defer c.Close()
	if !platform.SameUser(c, true) {
		return
	}
	id := random()[:24]
	h.mu.Lock()
	if h.closed {
		h.mu.Unlock()
		return
	}
	h.sessions[id] = c
	h.mu.Unlock()
	defer func() { h.mu.Lock(); delete(h.sessions, id); h.mu.Unlock() }()
	c.SetReadDeadline(time.Now().Add(10 * time.Second))
	r := bufio.NewReaderSize(c, 4096)
	raw, e := wire.Line(r, 4096)
	if e != nil {
		return
	}
	v, e := wire.Decode(raw, 4096)
	if e != nil || len(v) != 4 {
		return
	}
	token, _ := v["token"].(string)
	run, _ := v["run_id"].(string)
	nonce, _ := v["nonce"].(string)
	h.mu.Lock()
	a := h.runs[run]
	if a != nil && a.revoked {
		a = nil
	}
	h.mu.Unlock()
	if v["schema_version"] != "aevora.runtime-auth/1" || a == nil || len(nonce) != 64 || len(token) != len(a.token) || subtle.ConstantTimeCompare([]byte(token), []byte(a.token)) != 1 {
		return
	}
	if _, e = hex.DecodeString(nonce); e != nil {
		return
	}
	h.mu.Lock()
	replay := h.nonces[nonce] || len(h.nonces) >= 4096
	if !replay {
		h.nonces[nonce] = true
	}
	h.mu.Unlock()
	if replay {
		return
	}
	if a.ctx != nil {
		stop := context.AfterFunc(a.ctx, func() { c.Close() })
		defer stop()
	}
	if e = a.journal.Event("SESSION_AUTHORIZED", id, "", "ACTIVE"); e != nil {
		return
	}
	c.SetWriteDeadline(time.Now().Add(10 * time.Second))
	if _, e = c.Write([]byte("{\"status\":\"READY\"}\n")); e != nil {
		return
	}
	c.SetDeadline(time.Time{})
	s, err := h.server(id, a)
	if err != nil {
		return
	}
	stream := &boundedConn{Conn: c, reader: r, host: h, session: id, journal: a.journal, ids: map[string]bool{}, closed: make(chan struct{})}
	_, err = s.Connect(ctx, &mcp.IOTransport{Reader: stream, Writer: stream, MaxLineLength: wire.MaxMessage}, nil)
	if err != nil {
		return
	}
	// The connection is closed by SDK EOF, scope revocation or Host shutdown.
	<-stream.done()
}

func (h *Host) server(session string, selected ...*authorization) (*mcp.Server, error) {
	a := &authorization{scope: h.scope, engine: h.engine, journal: h.journal}
	if len(selected) > 0 {
		a = selected[0]
	}
	var data struct {
		Catalogs     map[string][]*mcp.Tool `json:"catalogs"`
		Instructions string                 `json:"instructions"`
	}
	raw, e := contracts.Files.ReadFile("tools.json")
	if e != nil {
		return nil, e
	}
	if e = json.Unmarshal(raw, &data); e != nil {
		return nil, e
	}
	s := mcp.NewServer(&mcp.Implementation{Name: "Aevora", Version: buildinfo.Version}, &mcp.ServerOptions{SupportedProtocolVersions: []string{"2025-11-25"}, Instructions: data.Instructions, Logger: slog.New(slog.NewTextHandler(io.Discard, nil))})
	key := "default"
	if a.scope.Proposals {
		key = "proposals"
	}
	active := make(chan struct{}, 1)
	for _, tool := range data.Catalogs[key] {
		name := tool.Name
		mcp.AddTool(s, tool, func(ctx context.Context, req *mcp.CallToolRequest, _ map[string]any) (*mcp.CallToolResult, any, error) {
			h.mu.Lock()
			if h.closed || a.revoked {
				h.mu.Unlock()
				return nil, nil, engine.ErrNotDispatched
			}
			h.operations.Add(1)
			h.toolCalls++
			a.calls.Add(1)
			h.mu.Unlock()
			defer h.operations.Done()
			defer a.calls.Done()
			select {
			case active <- struct{}{}:
				defer func() { <-active }()
			default:
				return nil, nil, errors.New("AEVORA_SESSION_BUSY")
			}
			ctx, cancel := context.WithTimeout(ctx, 60*time.Second)
			defer cancel()
			stop := context.AfterFunc(h.stopContext, cancel)
			defer stop()
			if a.ctx != nil {
				stopRun := context.AfterFunc(a.ctx, cancel)
				defer stopRun()
			}
			id := random()
			if err := a.journal.Event("OPERATION", session, id, "QUEUED"); err != nil {
				return nil, nil, errors.New("AEVORA_AUDIT_WRITE_FAILED")
			}
			var dispatched atomic.Bool
			result, err := a.engine.Call(ctx, a.scope, engine.Request{ID: id, Operation: name, Arguments: req.Params.Arguments, ValidateResult: func(raw json.RawMessage) error { _, e := toolResult(id, raw); return e }, BeforeDispatch: func() error {
				if ctx.Err() != nil {
					return engine.ErrNotDispatched
				}
				if e := a.journal.Event("OPERATION", session, id, "DISPATCHED"); e != nil {
					h.stopConnections()
					return e
				}
				dispatched.Store(true)
				return nil
			}})
			var value *mcp.CallToolResult
			if err == nil {
				value, err = toolResult(id, result)
				if err != nil {
					err = engine.ErrUnknown
				}
			}
			state := "COMPLETED"
			if err != nil {
				state = "FAILED_KNOWN"
				if dispatched.Load() && (errors.Is(err, engine.ErrUnknown) || ctx.Err() != nil) {
					state = "UNKNOWN"
				}
			}
			if e := a.journal.Event(name, session, id, state); e != nil {
				return nil, nil, engine.ErrUnknown
			}
			if err != nil {
				return &mcp.CallToolResult{Meta: mcp.Meta{"operation_id": id}, IsError: true, Content: []mcp.Content{&mcp.TextContent{Text: safeError(err)}}}, nil, nil
			}
			return value, nil, nil
		})
	}
	return s, nil
}

func safeError(err error) string {
	if err != nil && (err.Error() == "AEVORA_RUN_LIMIT" || err.Error() == "AEVORA_AUDIT_LIMIT" || err.Error() == "AEVORA_ROUTE_IN_USE" || err.Error() == "AEVORA_ROUTE_NOT_REMOVABLE") {
		return err.Error()
	}
	for _, e := range []error{engine.ErrUnknown, engine.ErrUnavailable, engine.ErrInvalid, engine.ErrRecord, engine.ErrNotDispatched, engine.ErrResultLimit, engine.ErrRunContext} {
		if errors.Is(err, e) {
			return e.Error()
		}
	}
	return "AEVORA_ENGINE_ERROR"
}
