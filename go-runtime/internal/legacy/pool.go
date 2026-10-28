// Package legacy runs trusted Python business code over private framed pipes.
package legacy

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"sync"
	"time"
)

type Options struct {
	Python, Host, Graph, PasswordFile string
	Port, Workers                     int
}
type worker struct {
	cmd    *exec.Cmd
	input  io.WriteCloser
	output io.ReadCloser
	once   sync.Once
}

func (w *worker) close() {
	w.once.Do(func() { w.input.Close(); terminate(w.cmd); w.output.Close(); w.cmd.Wait() })
}

type Pool struct {
	mu      sync.Mutex
	options Options
	scope   engine.RunContext
	owner   *os.File
	slots   chan *worker
	workers map[*worker]bool
	closed  bool
	cancel  context.CancelFunc
	ctx     context.Context
	binding string
}

func New(ctx context.Context, options Options, owner *os.File, scope engine.RunContext) (*Pool, error) {
	if runtime.GOOS == "windows" {
		return nil, errors.New("AEVORA_LEGACY_PLATFORM_UNSUPPORTED")
	}
	if !filepath.IsAbs(options.Python) || options.Workers < 1 || options.Workers > 4 || options.Host != "127.0.0.1" {
		return nil, errors.New("AEVORA_WORKER_CONFIGURATION_REQUIRED")
	}
	p := &Pool{options: options, scope: scope, owner: owner, slots: make(chan *worker, options.Workers), workers: map[*worker]bool{}}
	p.ctx, p.cancel = context.WithCancel(context.Background())
	for i := 0; i < options.Workers; i++ {
		w, e := p.start(ctx)
		if e != nil {
			p.Close()
			return nil, e
		}
		p.slots <- w
	}
	return p, nil
}

func (p *Pool) start(ctx context.Context) (*worker, error) {
	cmd := exec.Command(p.options.Python, "-I", "-m", "aevora.runtime_worker")
	// No model/provider environment or credential values enter the child.
	cmd.Env = []string{"PATH=/usr/bin:/bin", "LANG=C.UTF-8", "AEVORA_BACKEND_LOCK_FD=3", "AEVORA_FALKORDB_HOST=" + p.options.Host, "AEVORA_FALKORDB_PORT=" + strconv.Itoa(p.options.Port), "AEVORA_FALKORDB_GRAPH=" + p.options.Graph, "AEVORA_FALKORDB_PASSWORD_FILE=" + p.options.PasswordFile}
	for _, key := range []string{"HOME", "XDG_STATE_HOME"} {
		if value := os.Getenv(key); value != "" {
			cmd.Env = append(cmd.Env, key+"="+value)
		}
	}
	cmd.ExtraFiles = []*os.File{p.owner}
	configureProcess(cmd)
	cmd.Stderr = io.Discard
	in, e := cmd.StdinPipe()
	if e != nil {
		return nil, engine.ErrUnavailable
	}
	out, e := cmd.StdoutPipe()
	if e != nil {
		in.Close()
		return nil, engine.ErrUnavailable
	}
	if e = cmd.Start(); e != nil {
		in.Close()
		out.Close()
		return nil, engine.ErrUnavailable
	}
	w := &worker{cmd: cmd, input: in, output: out}
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		w.close()
		return nil, engine.ErrUnavailable
	}
	p.workers[w] = true
	p.mu.Unlock()
	boot := struct {
		Schema string `json:"schema_version"`
		engine.RunContext
	}{"aevora.worker-bootstrap/1", p.scope}
	ready := make(chan error, 1)
	go func() {
		if e := wire.WritePacket(in, boot); e != nil {
			ready <- e
			return
		}
		raw, e := wire.ReadPacket(out)
		if e == nil {
			var v map[string]any
			v, e = wire.Decode(raw, wire.MaxMessage)
			if e == nil {
				if v["error"] == engine.ErrRunContext.Error() {
					e = engine.ErrRunContext
				} else if v["schema_version"] != "aevora.worker-response/1" || v["status"] != "READY" {
					e = engine.ErrUnavailable
				} else {
					binding, ok := v["context_sha256"].(string)
					if !ok || len(binding) != 64 {
						e = engine.ErrUnavailable
					} else {
						p.mu.Lock()
						if p.binding != "" && p.binding != binding {
							e = engine.ErrRunContext
						} else {
							p.binding = binding
						}
						p.mu.Unlock()
					}
				}
			}
		}
		ready <- e
	}()
	timer := time.NewTimer(30 * time.Second)
	defer timer.Stop()
	select {
	case e = <-ready:
	case <-ctx.Done():
		e = ctx.Err()
	case <-p.ctx.Done():
		e = engine.ErrUnavailable
	case <-timer.C:
		e = engine.ErrUnavailable
	}
	if e != nil {
		p.remove(w)
		if errors.Is(e, engine.ErrRunContext) {
			return nil, e
		}
		return nil, engine.ErrUnavailable
	}
	return w, nil
}

func (p *Pool) remove(w *worker) { w.close(); p.mu.Lock(); delete(p.workers, w); p.mu.Unlock() }
func (p *Pool) Health(context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed || len(p.workers) == 0 {
		return engine.ErrUnavailable
	}
	return nil
}
func (p *Pool) RunBinding() string { p.mu.Lock(); defer p.mu.Unlock(); return p.binding }

func (p *Pool) Call(ctx context.Context, scope engine.RunContext, request engine.Request) (json.RawMessage, error) {
	a, _ := json.Marshal(scope)
	b, _ := json.Marshal(p.scope)
	if !bytes.Equal(a, b) {
		return nil, engine.ErrInvalid
	}
	var w *worker
	select {
	case w = <-p.slots:
	case <-ctx.Done():
		return nil, engine.ErrNotDispatched
	case <-p.ctx.Done():
		return nil, engine.ErrNotDispatched
	}
	defer func() { p.slots <- w }()
	p.mu.Lock()
	closed := p.closed
	p.mu.Unlock()
	if closed {
		return nil, engine.ErrNotDispatched
	}
	if w == nil {
		var e error
		w, e = p.start(ctx)
		if e != nil {
			return nil, engine.ErrNotDispatched
		}
	}
	if request.BeforeDispatch == nil {
		return nil, engine.ErrNotDispatched
	}
	if e := request.BeforeDispatch(); e != nil {
		return nil, engine.ErrNotDispatched
	}
	result := make(chan struct {
		raw []byte
		err error
	}, 1)
	go func(current *worker) {
		v := map[string]any{"schema_version": "aevora.worker-request/1", "request_id": request.ID, "operation": request.Operation, "arguments": request.Arguments}
		e := wire.WritePacket(current.input, v)
		var raw []byte
		if e == nil {
			raw, e = wire.ReadPacket(current.output)
		}
		result <- struct {
			raw []byte
			err error
		}{raw, e}
	}(w)
	var raw []byte
	var err error
	select {
	case r := <-result:
		raw, err = r.raw, r.err
	case <-ctx.Done():
		err = ctx.Err()
	case <-p.ctx.Done():
		err = engine.ErrUnknown
	}
	if err != nil {
		p.remove(w)
		w = nil
		return nil, engine.ErrUnknown
	}
	var response struct {
		Schema string          `json:"schema_version"`
		ID     string          `json:"request_id"`
		Status string          `json:"status"`
		Result json.RawMessage `json:"result"`
		Error  string          `json:"error"`
	}
	if json.Unmarshal(raw, &response) != nil || response.Schema != "aevora.worker-response/1" || response.ID != request.ID {
		p.remove(w)
		w = nil
		return nil, engine.ErrUnknown
	}
	if response.Status == "COMPLETED" {
		if _, e := wire.Decode(response.Result, wire.MaxMessage/4); e != nil {
			return nil, engine.ErrUnknown
		}
		return response.Result, nil
	}
	if response.Status == "UNKNOWN" {
		return nil, engine.ErrUnknown
	}
	if response.Status != "FAILED_KNOWN" {
		p.remove(w)
		w = nil
		return nil, engine.ErrUnknown
	}
	switch response.Error {
	case engine.ErrUnavailable.Error():
		return nil, engine.ErrUnavailable
	case engine.ErrRecord.Error():
		return nil, engine.ErrRecord
	case engine.ErrInvalid.Error():
		return nil, engine.ErrInvalid
	default:
		return nil, engine.ErrUnknown
	}
}

func (p *Pool) Close() error {
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		return nil
	}
	p.closed = true
	p.cancel()
	all := make([]*worker, 0, len(p.workers))
	for w := range p.workers {
		all = append(all, w)
	}
	p.mu.Unlock()
	for _, w := range all {
		p.remove(w)
	}
	return nil
}
