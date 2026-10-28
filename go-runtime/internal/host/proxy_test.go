package host

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

type proxyCapture struct {
	sync.Mutex
	bytes.Buffer
}

func (b *proxyCapture) Write(p []byte) (int, error) {
	b.Lock()
	defer b.Unlock()
	return b.Buffer.Write(p)
}
func (b *proxyCapture) text() string { b.Lock(); defer b.Unlock(); return b.Buffer.String() }

func TestProxyNeverReplaysAWriteWhoseResponseWasLost(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	var calls, dials atomic.Int32
	dial := func(c context.Context) (*proxyUpstream, error) {
		index := dials.Add(1)
		left, right := net.Pipe()
		server := mcp.NewServer(&mcp.Implementation{Name: "controlled-upstream", Version: "1"}, nil)
		server.AddTool(&mcp.Tool{Name: "write_observation", InputSchema: map[string]any{"type": "object"}}, func(c context.Context, _ *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			calls.Add(1)
			if index == 1 {
				left.Close()
				return nil, errors.New("controlled response loss after effect")
			}
			return toolResult("controlled", json.RawMessage(`{"large":9007199254740993}`))
		})
		st, ct := &mcp.IOTransport{Reader: left, Writer: left}, &mcp.IOTransport{Reader: right, Writer: right}
		ss, err := server.Connect(ctx, st, nil)
		if err != nil {
			return nil, err
		}
		cs, err := mcp.NewClient(&mcp.Implementation{Name: "controlled-proxy", Version: "1"}, nil).Connect(c, ct, &mcp.ClientSessionOptions{ProtocolVersion: "2025-11-25"})
		if err != nil {
			ss.Close()
			return nil, err
		}
		return &proxyUpstream{session: cs, close: func() { cs.Close(); ss.Close() }}, nil
	}
	inR, inW := io.Pipe()
	outR, outW := io.Pipe()
	done := make(chan error, 1)
	capture := &proxyCapture{}
	// Record the exact wire bytes before delivering them. Writing to outW first
	// lets CallTool return while MultiWriter has not yet updated capture.
	go func() { defer outW.Close(); done <- serveProxy(ctx, dial, inR, io.MultiWriter(capture, outW)) }()
	session, err := mcp.NewClient(&mcp.Implementation{Name: "same-client", Version: "1"}, nil).Connect(ctx, &mcp.IOTransport{Reader: outR, Writer: inW}, &mcp.ClientSessionOptions{ProtocolVersion: "2025-11-25"})
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		session.Close()
		inW.Close()
		outR.Close()
		cancel()
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Fatal("proxy leaked")
		}
	}()
	result, err := session.CallTool(ctx, &mcp.CallToolParams{Name: "write_observation", Arguments: map[string]any{}})
	if err != nil || !result.IsError || calls.Load() != 1 || dials.Load() != 1 {
		t.Fatal("write replayed or downstream lost", result, err, calls.Load(), dials.Load())
	}
	if !strings.Contains(result.Content[0].(*mcp.TextContent).Text, "OUTCOME_UNKNOWN") {
		t.Fatal("lost response treated as failure before dispatch")
	}
	result, err = session.CallTool(ctx, &mcp.CallToolParams{Name: "write_observation", Arguments: map[string]any{}})
	if err != nil || result.IsError || calls.Load() != 2 || dials.Load() != 2 {
		t.Fatal("explicit later call did not reconnect", result, err, calls.Load(), dials.Load())
	}
	if !strings.Contains(capture.text(), `"large":9007199254740993`) {
		t.Fatal("proxy rounded structured factual integer", capture.text())
	}
}
