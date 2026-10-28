//go:build linux

package host

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestTaskRevocationKeepsDispatchedOperationUnknownWithoutReplay(t *testing.T) {
	p := profile(t)
	p.Schema = "aevora.host-config/2"
	p.Database.Kind = "sqlite"
	p.Database.Path = filepath.Join(filepath.Dir(p.Session.Root), "experience.db")
	db, e := storage.Open(context.Background(), p.Database.Path, storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	db.Close()
	blocked := &closingEngine{started: make(chan struct{}), finished: make(chan struct{})}
	calls := 0
	factory := func(_ context.Context, _ *os.File, _ Profile, s engine.RunContext) (engine.Engine, error) {
		if s.RunID == "task-interrupted" {
			calls++
			if calls == 1 {
				return blocked, nil
			}
		}
		return fixtureEngine{}, nil
	}
	h, e := New(context.Background(), p, "host", false, factory)
	if e != nil {
		t.Fatal(e)
	}
	defer h.Close()
	go h.Serve(context.Background())
	if _, e = h.RegisterRun(context.Background(), "task-interrupted", json.RawMessage(`{}`), false); e != nil {
		t.Fatal(e)
	}
	a := h.runs["task-interrupted"]
	c, e := net.Dial("unix", filepath.Join(h.folder, "mcp.sock"))
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	auth, _ := json.Marshal(map[string]any{"schema_version": "aevora.runtime-auth/1", "run_id": a.scope.RunID, "token": a.token, "nonce": random()})
	c.Write(append(auth, '\n'))
	if _, e = wire.Line(bufio.NewReader(c), 4096); e != nil {
		t.Fatal(e)
	}
	session, e := mcp.NewClient(&mcp.Implementation{Name: "revocation-contract", Version: "1"}, nil).Connect(context.Background(), &mcp.IOTransport{Reader: c, Writer: c}, nil)
	if e != nil {
		t.Fatal(e)
	}
	defer session.Close()
	go session.CallTool(context.Background(), &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}}})
	select {
	case <-blocked.started:
	case <-time.After(3 * time.Second):
		t.Fatal("not dispatched")
	}
	before := h.Snapshot()
	if _, e = h.CloseRun(a.scope.RunID); e != nil {
		t.Fatal(e)
	}
	select {
	case <-blocked.finished:
	default:
		t.Fatal("task close did not drain operation")
	}
	if _, e = os.Stat(filepath.Join(a.folder, "grant.json")); !os.IsNotExist(e) {
		t.Fatal("revoked grant remains", e)
	}
	raw, e := os.ReadFile(filepath.Join(a.folder, "mcp_events.jsonl"))
	if e != nil {
		t.Fatal(e)
	}
	id := ""
	scanner := bufio.NewScanner(bytes.NewReader(raw))
	for scanner.Scan() {
		var v map[string]any
		if json.Unmarshal(scanner.Bytes(), &v) == nil && v["state"] == "DISPATCHED" {
			id, _ = v["operation_id"].(string)
		}
	}
	if id == "" {
		t.Fatal("operation identity lost")
	}
	state, e := OperationStatus(a.folder, id)
	if e != nil || state["state"] != "UNKNOWN" || state["automatic_replay"] != false {
		t.Fatal(state, e)
	}
	if _, e = h.RegisterRun(context.Background(), a.scope.RunID, json.RawMessage(`{}`), false); e != nil {
		t.Fatal(e)
	}
	fresh := h.runs[a.scope.RunID]
	if fresh.folder == a.folder || fresh.token == a.token {
		t.Fatal("resume reused revoked grant")
	}
	after := h.Snapshot()
	if after.Budget["frames"] != before.Budget["frames"] || after.Budget["consumer_nonces"] != before.Budget["consumer_nonces"] || after.ToolCalls != before.ToolCalls {
		t.Fatal("resume reset budget or replayed tool")
	}
	preserved, e := os.ReadFile(filepath.Join(a.folder, "mcp_events.jsonl"))
	if e != nil || string(raw) != string(preserved) {
		t.Fatal("closed operation journal rewritten", e)
	}
}
