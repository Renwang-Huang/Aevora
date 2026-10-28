//go:build linux

package legacy

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// The fixture emulates only the private pipe contract, never graph semantics.
const pipeFixture = `#!/usr/bin/python3
import json, struct, sys, time
def read():
    h=sys.stdin.buffer.read(4)
    if len(h)!=4: raise SystemExit(0)
    return json.loads(sys.stdin.buffer.read(struct.unpack('>I',h)[0]))
def write(v):
    b=json.dumps(v).encode();sys.stdout.buffer.write(struct.pack('>I',len(b))+b);sys.stdout.buffer.flush()
bootstrap=read()
write({'schema_version':'aevora.worker-response/1','status':'READY','context_sha256':'a'*64})
while True:
    v=read()
    if v['operation']=='wait': time.sleep(5)
    write({'schema_version':'aevora.worker-response/1','request_id':v['request_id'],'status':'COMPLETED','result':{'status':'AVAILABLE','facts':bootstrap['facts'],'argument_type':type(v['arguments'].get('x')).__name__}})
`

func TestPoolCancellationDoesNotReplayOrCancelAnotherSlot(t *testing.T) {
	dir := t.TempDir()
	python := filepath.Join(dir, "python")
	if err := os.WriteFile(python, []byte(pipeFixture), 0700); err != nil {
		t.Fatal(err)
	}
	owner, err := os.CreateTemp(dir, "owner")
	if err != nil {
		t.Fatal(err)
	}
	defer owner.Close()
	scope := engine.RunContext{BackendID: "backend", WorkspaceID: "workspace", RunID: "run", Facts: json.RawMessage(`{"worker_count":9007199254740993}`)}
	p, err := New(context.Background(), Options{Python: python, Host: "127.0.0.1", Port: 17790, Graph: "test", Workers: 2}, owner, scope)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	dispatched := make(chan struct{})
	done := make(chan error, 1)
	go func() {
		_, err := p.Call(ctx, scope, engine.Request{ID: strings.Repeat("a", 64), Operation: "wait", Arguments: json.RawMessage(`{}`), BeforeDispatch: func() error { close(dispatched); return nil }})
		done <- err
	}()
	select {
	case <-dispatched:
	case <-time.After(3 * time.Second):
		t.Fatal("not dispatched")
	}
	b, err := p.Call(context.Background(), scope, engine.Request{ID: strings.Repeat("b", 64), Operation: "resolve_experience", Arguments: json.RawMessage(`{"x":1.0}`), BeforeDispatch: func() error { return nil }})
	if err != nil || !strings.Contains(string(b), `9007199254740993`) || !strings.Contains(string(b), `"argument_type": "float"`) {
		t.Fatalf("unrelated slot failed: %s %v", b, err)
	}
	cancel()
	select {
	case err := <-done:
		if !errors.Is(err, engine.ErrUnknown) {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("canceled slot not reaped")
	}
}
