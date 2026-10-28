package host

import (
	"context"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
)

// Probe uses the actual scoped IPC connector and official SDK. Ping/list-tools
// do not create Query/Decision/Outcome records or exercise an external model.
func Probe(ctx context.Context, p Profile) (map[string]any, error) {
	return ProbeRun(ctx, p, "")
}
func ProbeRun(ctx context.Context, p Profile, run string) (map[string]any, error) {
	return probeConnection(ctx, p, run, false)
}
func ProbeAutomatic(ctx context.Context, p Profile) (map[string]any, error) {
	return probeConnection(ctx, p, "", true)
}
func probeConnection(ctx context.Context, p Profile, run string, automatic bool) (map[string]any, error) {
	inputR, inputW := io.Pipe()
	outputR, outputW := io.Pipe()
	defer inputW.Close()
	defer outputR.Close()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	done := make(chan error, 1)
	go func() {
		defer inputR.Close()
		defer outputW.Close()
		if automatic {
			done <- PersistentBridge(ctx, p.Session.Root, "", "", true, inputR, outputW)
		} else {
			done <- BridgeRun(ctx, p.Session.Root, run, inputR, outputW)
		}
	}()
	defer func() { cancel(); inputW.Close(); outputR.Close(); <-done }()
	client := mcp.NewClient(&mcp.Implementation{Name: "aevora-doctor", Version: "1"}, nil)
	session, e := client.Connect(ctx, &mcp.IOTransport{Reader: outputR, Writer: inputW}, &mcp.ClientSessionOptions{ProtocolVersion: "2025-11-25"})
	if e != nil {
		return nil, e
	}
	defer session.Close()
	tools, e := session.ListTools(ctx, nil)
	if e != nil {
		return nil, e
	}
	if e = session.Ping(ctx, nil); e != nil {
		return nil, e
	}
	names := []string{}
	for _, v := range tools.Tools {
		names = append(names, v.Name)
	}
	return map[string]any{"status": "READY", "protocol": "2025-11-25", "tools": names, "probe": "ACTUAL_INITIALIZE_LIST_TOOLS_PING; NO_RESOLVER_OR_MODEL_CALL"}, nil
}
