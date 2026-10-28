package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"io"
	"net/http"
	"strings"
	"time"
)

func doctor(ctx context.Context, p host.Profile, response map[string]any) error {
	var result domain.Map
	if raw, ok := response["result"].(json.RawMessage); ok {
		value, e := codec.Parse(raw)
		if e != nil {
			return e
		}
		result = domain.M(value)
	} else {
		result = domain.M(response["result"])
	}
	if result == nil {
		return domain.ErrInvalid
	}
	probeCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	mcp, e := host.Probe(probeCtx, p)
	if e != nil {
		mcp = domain.Map{"status": "UNAVAILABLE", "probe": "ATTEMPTED; HOST_MAY_BE_STOPPED"}
	}
	result["mcp"] = mcp
	console, e := consoleProbe(ctx, p)
	if e != nil {
		return e
	}
	result["console"] = console
	result["runtime_ready"] = "NOT_PROVEN"
	if result["database"] == "READY" && mcp["status"] == "READY" && console["status"] == "READY" {
		result["runtime_ready"] = "READY"
	}
	response["result"] = result
	return nil
}

func consoleProbe(ctx context.Context, p host.Profile) (domain.Map, error) {
	transport := &http.Transport{Proxy: nil, DisableKeepAlives: true}
	defer transport.CloseIdleConnections()
	client := http.Client{Transport: transport, Timeout: 3 * time.Second}
	endpoint := fmt.Sprintf("http://127.0.0.1:%d", p.Console.Port)
	if runtime, e := host.ReadStatus(p); e == nil && runtime.State == "READY" && strings.HasPrefix(runtime.Console, "http://127.0.0.1:") {
		endpoint = runtime.Console
	}
	request, e := http.NewRequestWithContext(ctx, "GET", endpoint+"/api/health", nil)
	if e != nil {
		return nil, e
	}
	console := domain.Map{"status": "UNAVAILABLE", "probe": "ATTEMPTED; CHECK_ACTUAL_SERVE_URL_IF_PORT_OVERRIDDEN"}
	resp, e := client.Do(request)
	if e == nil {
		raw, err := io.ReadAll(io.LimitReader(resp.Body, 65537))
		resp.Body.Close()
		if err == nil && resp.StatusCode == 200 {
			body, err := wire.Decode(raw, 65536)
			if err == nil && body["mode"] == "LIVE" && domain.M(body["data"])["database"] == "AVAILABLE" && domain.M(body["data"])["backend_id"] == host.BackendID(p) {
				console = domain.Map{"status": "READY", "probe": "ACTUAL_LIVE_HEALTH; BACKEND_ID_MATCHED"}
			}
		}
	}
	return console, nil
}
