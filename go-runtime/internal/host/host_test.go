//go:build linux

package host

import (
	"bufio"
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type fixtureEngine struct{}

func (fixtureEngine) RunBinding() string { return strings.Repeat("a", 64) }

func (fixtureEngine) Health(context.Context) error { return nil }
func (fixtureEngine) Close() error                 { return nil }
func (fixtureEngine) Call(_ context.Context, s engine.RunContext, r engine.Request) (json.RawMessage, error) {
	if r.BeforeDispatch != nil {
		if err := r.BeforeDispatch(); err != nil {
			return nil, err
		}
	}
	return json.Marshal(map[string]any{"status": "AVAILABLE", "run_id": s.RunID, "candidates": []any{}})
}

func TestOperationStatusPreservesUnknownAndTransportDistinction(t *testing.T) {
	p := profile(t)
	if err := os.Mkdir(p.Session.Root, 0700); err != nil {
		t.Fatal(err)
	}
	j, err := newJournal(filepath.Join(p.Session.Root, "mcp_events.jsonl"), "run")
	if err != nil {
		t.Fatal(err)
	}
	defer j.Close()
	id := strings.Repeat("a", 64)
	if err = j.Event("OPERATION", "session", id, "DISPATCHED"); err != nil {
		t.Fatal(err)
	}
	v, err := OperationStatus(p.Session.Root, id)
	if err != nil || v["state"] != "UNKNOWN" || v["response_written_to_transport"] != false {
		t.Fatalf("unknown lost: %v %v", v, err)
	}
	j.Event("resolve_experience", "session", id, "COMPLETED")
	j.Event("RESPONSE", "session", id, "WRITTEN_TO_TRANSPORT")
	v, err = OperationStatus(p.Session.Root, id)
	if err != nil || v["state"] != "COMPLETED" || v["response_written_to_transport"] != true || v["database_persistence"] != "NOT_CONFIRMED" {
		t.Fatalf("completion overstated: %v %v", v, err)
	}
}

func profile(t *testing.T) Profile {
	t.Helper()
	base, err := os.MkdirTemp("", "av-host-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(base) })
	t.Setenv("XDG_STATE_HOME", filepath.Join(base, "state"))
	previous := ownershipHome
	ownershipHome = func() string { return filepath.Join(base, "state") }
	t.Cleanup(func() { ownershipHome = previous })
	var p Profile
	p.Schema = "aevora.host-config/1"
	p.Database.Host = "127.0.0.1"
	p.Database.Port = 17790
	p.Database.Graph = "test"
	p.Session.Root = filepath.Join(base, "sessions")
	p.Session.Facts = json.RawMessage(`{}`)
	return p
}

func client(t *testing.T, h *Host) *mcp.ClientSession {
	t.Helper()
	c, err := net.Dial("unix", filepath.Join(h.folder, "mcp.sock"))
	if err != nil {
		t.Fatal(err)
	}
	a, _ := json.Marshal(map[string]any{"schema_version": "aevora.runtime-auth/1", "run_id": h.scope.RunID, "token": h.token, "nonce": random()})
	c.Write(append(a, '\n'))
	r := bufio.NewReader(c)
	if _, err = wire.Line(r, 4096); err != nil {
		t.Fatal(err)
	}
	// bufio has consumed only the authentication reply; SDK writes begin next.
	s, err := mcp.NewClient(&mcp.Implementation{Name: "contract-client", Version: "1"}, nil).Connect(context.Background(), &mcp.IOTransport{Reader: c, Writer: c}, &mcp.ClientSessionOptions{ProtocolVersion: "2025-11-25"})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func TestHostUsesOfficialSDKAndRetainsEvidence(t *testing.T) {
	p := profile(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	h, err := New(ctx, p, "trusted-run", false, func(context.Context, *os.File, Profile, engine.RunContext) (engine.Engine, error) {
		return fixtureEngine{}, nil
	})
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan error, 1)
	go func() { done <- h.Serve(ctx) }()
	a := client(t, h)
	b := client(t, h)
	tools, err := b.ListTools(ctx, nil)
	if err != nil || len(tools.Tools) != 6 {
		t.Fatalf("catalog: %v %v", tools, err)
	}
	a.Close()
	result, err := b.CallTool(ctx, &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}}})
	if err != nil || result.IsError {
		t.Fatalf("call: %v %v", result, err)
	}
	cancel()
	if err = h.Close(); err != nil {
		t.Fatal(err)
	}
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Fatal("Host did not stop")
	}
	if _, err = os.Stat(filepath.Join(h.folder, "grant.json")); !os.IsNotExist(err) {
		t.Fatal("grant remains")
	}
	if raw, err := os.ReadFile(filepath.Join(h.folder, "mcp_events.jsonl")); err != nil || len(raw) == 0 {
		t.Fatal("evidence lost")
	}
}

func TestBackendOwnershipCannotMoveToAnotherRoot(t *testing.T) {
	p := profile(t)
	if err := os.MkdirAll(p.Session.Root, 0700); err != nil {
		t.Fatal(err)
	}
	owner, err := Own(p)
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("XDG_STATE_HOME", filepath.Join(filepath.Dir(p.Session.Root), "another-state-namespace"))
	if f, err := Own(p); err == nil {
		f.Close()
		t.Fatal("second writer acquired ownership")
	}
	owner.Close()
	p.Session.Root = filepath.Join(filepath.Dir(p.Session.Root), "another")
	os.Mkdir(p.Session.Root, 0700)
	if f, err := Own(p); err == nil {
		f.Close()
		t.Fatal("backend root silently rebound")
	}
}

type closingEngine struct {
	fixtureEngine
	started, finished chan struct{}
}

func (e *closingEngine) Call(ctx context.Context, _ engine.RunContext, r engine.Request) (json.RawMessage, error) {
	if err := r.BeforeDispatch(); err != nil {
		return nil, err
	}
	close(e.started)
	<-ctx.Done()
	close(e.finished)
	return nil, engine.ErrUnknown
}

func TestCloseDrainsOperationBeforeClosingAudit(t *testing.T) {
	p := profile(t)
	e := &closingEngine{started: make(chan struct{}), finished: make(chan struct{})}
	h, err := New(context.Background(), p, "closing-run", false, func(context.Context, *os.File, Profile, engine.RunContext) (engine.Engine, error) { return e, nil })
	if err != nil {
		t.Fatal(err)
	}
	served := make(chan error, 1)
	go func() { served <- h.Serve(context.Background()) }()
	session := client(t, h)
	go session.CallTool(context.Background(), &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}}})
	select {
	case <-e.started:
	case <-time.After(3 * time.Second):
		t.Fatal("operation did not start")
	}
	closed := make(chan error, 1)
	go func() { closed <- h.Close() }()
	select {
	case err := <-closed:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("close did not cancel and drain")
	}
	select {
	case <-e.finished:
	default:
		t.Fatal("engine operation still active")
	}
	raw, err := os.ReadFile(filepath.Join(h.folder, "mcp_events.jsonl"))
	if err != nil || !strings.Contains(string(raw), `"state":"UNKNOWN"`) {
		t.Fatalf("unknown terminal audit missing: %v", err)
	}
	select {
	case <-served:
	case <-time.After(time.Second):
		t.Fatal("serve watcher remains")
	}
}
