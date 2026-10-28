package host

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/buildinfo"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type proxyUpstream struct {
	session *mcp.ClientSession
	close   func()
}
type proxyDial func(context.Context) (*proxyUpstream, error)
type proxyInput struct{ io.Reader }

func (p proxyInput) Close() error {
	if c, ok := p.Reader.(io.Closer); ok {
		return c.Close()
	}
	return nil
}

type proxyOutput struct{ io.Writer }

func (p proxyOutput) Close() error {
	if c, ok := p.Writer.(io.Closer); ok {
		return c.Close()
	}
	return nil
}

func rawUpstream(ctx context.Context, root, run, grant string) (*proxyUpstream, error) {
	lifetime, cancel := context.WithCancel(context.Background())
	inR, inW := io.Pipe()
	outR, outW := io.Pipe()
	done := make(chan struct{})
	go func() {
		defer close(done)
		defer outW.Close()
		defer inR.Close()
		if grant != "" {
			BridgeGrant(lifetime, grant, inR, outW)
		} else {
			BridgeRun(lifetime, root, run, inR, outW)
		}
	}()
	cleanup := func() {
		cancel()
		inW.Close()
		outR.Close()
		select {
		case <-done:
		case <-time.After(time.Second):
		}
	}
	client := mcp.NewClient(&mcp.Implementation{Name: "Aevora-connector", Version: buildinfo.Version}, nil)
	session, err := client.Connect(ctx, &mcp.IOTransport{Reader: outR, Writer: inW, MaxLineLength: wire.MaxMessage}, &mcp.ClientSessionOptions{ProtocolVersion: "2025-11-25"})
	if err != nil {
		cleanup()
		return nil, err
	}
	return &proxyUpstream{session: session, close: func() { session.Close(); cleanup() }}, nil
}

// PersistentBridge terminates the downstream MCP lifecycle independently of
// each Host epoch. Only authentication/initialization and ping are retried.
// A tools/call is sent once: a lost response is UNKNOWN, never replayed.
func PersistentBridge(ctx context.Context, root, run, grant string, automatic bool, input io.Reader, output io.Writer) error {
	return persistentBridge(ctx, root, run, grant, automatic, "", input, output)
}

// The connector's cwd is a routing hint only; the Host checks authorization
// and measures the project independently. A process retains its selected
// project for the lifetime of its Run, including reconnect and close.
func PersistentWorkspaceBridge(ctx context.Context, root string, input io.Reader, output io.Writer) error {
	directory, err := os.Getwd()
	if err != nil {
		return err
	}
	project, err := local.SelectAutomaticWorkspace(root, directory)
	if errors.Is(err, local.ErrProjectNotRegistered) {
		return persistentBridge(ctx, root, "", "", true, unregisteredWorkspace, input, output)
	}
	if err != nil {
		return err
	}
	return persistentBridge(ctx, root, "", "", true, project.Name, input, output)
}

func persistentBridge(ctx context.Context, root, run, grant string, automatic bool, project string, input io.Reader, output io.Writer) error {
	name := ""
	dial := func(c context.Context) (*proxyUpstream, error) {
		if automatic {
			result, err := AutomaticProjectCall(c, root, name, project, "auto-open")
			if err != nil {
				return nil, err
			}
			name, _ = result["task_name"].(string)
			run, _ = result["run_id"].(string)
		} else if grant != "" || run == "" {
			path := grant
			if path == "" {
				path = filepath.Join(root, "current.json")
			}
			raw, err := platform.ReadPrivate(path, 4096)
			if err != nil {
				return nil, err
			}
			value, err := wire.Decode(raw, 4096)
			if err != nil {
				return nil, err
			}
			selected, _ := value["run_id"].(string)
			if !validID.MatchString(selected) || run != "" && run != selected {
				return nil, engine.ErrRunContext
			}
			run = selected
		}
		return rawUpstream(c, root, run, grant)
	}
	if automatic {
		defer func() {
			if name != "" {
				c, cancel := context.WithTimeout(context.Background(), 3*time.Second)
				defer cancel()
				AutomaticProjectCall(c, root, name, project, "auto-close")
			}
		}()
	}
	extra := ""
	if project == unregisteredWorkspace {
		extra = " This session's working directory is not a registered project. Only Host runtime facts are available; target project, version, and workspace facts are unknown. Register this workspace to obtain measured target context."
	}
	return serveProxyWithInstructions(ctx, dial, input, output, extra)
}

func serveProxy(ctx context.Context, dial proxyDial, input io.Reader, output io.Writer) error {
	return serveProxyWithInstructions(ctx, dial, input, output, "")
}

func serveProxyWithInstructions(ctx context.Context, dial proxyDial, input io.Reader, output io.Writer, extra string) error {
	var lock sync.Mutex
	initial, cancel := context.WithTimeout(ctx, 10*time.Second)
	up, err := dial(initial)
	cancel()
	if err != nil {
		return err
	}
	defer func() {
		lock.Lock()
		defer lock.Unlock()
		if up != nil {
			up.close()
		}
	}()
	catalog, err := up.session.ListTools(ctx, nil)
	if err != nil {
		return err
	}
	server := mcp.NewServer(&mcp.Implementation{Name: "Aevora", Version: buildinfo.Version}, &mcp.ServerOptions{SupportedProtocolVersions: []string{"2025-11-25"}, Instructions: up.session.InitializeResult().Instructions + extra, Logger: slog.New(slog.NewTextHandler(io.Discard, nil))})
	for _, tool := range catalog.Tools {
		server.AddTool(tool, func(c context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			lock.Lock()
			defer lock.Unlock()
			if up != nil {
				probe, stop := context.WithTimeout(c, 2*time.Second)
				e := up.session.Ping(probe, nil)
				stop()
				if e != nil {
					up.close()
					up = nil
				}
			}
			if up == nil {
				connect, stop := context.WithTimeout(c, 5*time.Second)
				defer stop()
				up, err = dial(connect)
				if err != nil {
					return proxyFailure("AEVORA_RECONNECT_REQUIRED", "Host or Run authorization is unavailable. Start the owned Host or establish a new task if its context changed; this request was not dispatched."), nil
				}
			}
			result, e := up.session.CallTool(c, &mcp.CallToolParams{Name: req.Params.Name, Arguments: req.Params.Arguments})
			if e != nil {
				up.close()
				up = nil
				return proxyFailure("AEVORA_RESPONSE_LOST_OUTCOME_UNKNOWN", "The call was not replayed. Inspect operation evidence before retrying writes; a subsequent new call can reconnect."), nil
			}
			// The Host emits exact canonical JSON as text. Restore number tokens
			// after the SDK's generic structured-content decoding so this extra
			// transport hop cannot round large factual integers or their hashes.
			if !result.IsError && result.StructuredContent != nil && len(result.Content) == 1 {
				if text, ok := result.Content[0].(*mcp.TextContent); ok {
					if exact, e := codec.Parse([]byte(text.Text)); e == nil {
						result.StructuredContent = exact
					}
				}
			}
			return result, nil
		})
	}
	return server.Run(ctx, &mcp.IOTransport{Reader: proxyInput{input}, Writer: proxyOutput{output}, MaxLineLength: wire.MaxMessage})
}
func proxyFailure(code, next string) *mcp.CallToolResult {
	return &mcp.CallToolResult{IsError: true, Content: []mcp.Content{&mcp.TextContent{Text: code + ": " + next}}}
}
