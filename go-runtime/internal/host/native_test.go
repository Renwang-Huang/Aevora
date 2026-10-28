package host_test

import (
	"bufio"
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestNativeRunsAndTrustedManagementUseSeparateAuthority(t *testing.T) {
	base, err := os.MkdirTemp("", "av-mgr-")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(base)
	root := filepath.Join(base, "owned")
	if e := platform.PrivateDir(root, true); e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	path := filepath.Join(root, "experience.db")
	db, e := storage.Open(ctx, path, storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	var candidateID string
	if e = db.Write(ctx, func(raw *storage.Repository) error {
		body := domain.Map{"candidate_key": "usage", "title": "Queue investigation", "strategy": "Inspect source", "public_summary": "Fixture observation", "necessary_conditions": domain.Map{}, "scope": domain.Map{}, "inapplicable_conditions": domain.Map{}, "unknown_fields": []any{}, "limitations": []any{}, "source_references": []any{}}
		result, err := (domain.Repo{Repository: raw}).Propose(ctx, "fixture-source", body)
		if err == nil {
			candidateID = domain.S(result["candidate_id"])
		}
		return err
	}); e != nil {
		t.Fatal(e)
	}
	db.Close()
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind, p.Database.Path = "sqlite", path
	p.Session.Root = filepath.Join(root, "sessions")
	p.Session.Facts = json.RawMessage(`{"worker_count":1.0}`)
	p.Console.Port = 17805
	id := host.BackendID(p)
	defer func() {
		directory := host.RegistryDir(id)
		for _, name := range []string{"management.json", "binding.json", "runtime.json"} {
			os.Remove(filepath.Join(directory, name))
		}
		os.Remove(directory)
	}()
	h, e := host.New(ctx, p, "run-a", false, native.Factory())
	if e != nil {
		t.Fatal(e)
	}
	defer func() {
		h.Close()
	}()
	if e = h.Ready("http://127.0.0.1:17805"); e != nil {
		t.Fatal(e)
	}
	beforeStatus := h.Snapshot()
	for range 20 {
		if _, e = host.ReadStatus(p); e != nil {
			t.Fatal(e)
		}
	}
	afterStatus := h.Snapshot()
	if beforeStatus.Budget["frames"] != afterStatus.Budget["frames"] || beforeStatus.Budget["management_nonces"] != afterStatus.Budget["management_nonces"] || beforeStatus.ToolCalls != afterStatus.ToolCalls {
		t.Fatal("reading status consumed authority budget")
	}
	served := make(chan error, 1)
	go func() { served <- h.Serve(ctx) }()
	response, e := host.ManagementCall(ctx, p, "run-b", "open-run", map[string]any{"public_context": json.RawMessage(`{"worker_count":2.0}`), "enable_proposals": false})
	if e != nil || response["status"] != "COMPLETED" {
		t.Fatal(response, e)
	}
	response, e = host.ManagementCall(ctx, p, "run-b", "query", map[string]any{"task_context": map[string]any{}})
	if e != nil || response["status"] != "COMPLETED" {
		t.Fatal(response, e)
	}
	result := response["result"].(map[string]any)
	if result["run_id"] != "run-b" {
		t.Fatal("management used another Run")
	}
	raw, e := os.ReadFile(filepath.Join(h.Folder(), "grant.json"))
	if e != nil {
		t.Fatal(e)
	}
	var grant map[string]any
	if e = json.Unmarshal(raw, &grant); e != nil {
		t.Fatal(e)
	}
	c, e := platform.Dial(ctx, grant["socket"].(string))
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	auth, _ := json.Marshal(map[string]any{"schema_version": "aevora.runtime-auth/1", "run_id": "run-a", "token": grant["token"], "nonce": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"})
	if _, e = c.Write(append(auth, '\n')); e != nil {
		t.Fatal(e)
	}
	reader := bufio.NewReader(c)
	if _, e = reader.ReadBytes('\n'); e != nil {
		t.Fatal(e)
	}
	client := mcp.NewClient(&mcp.Implementation{Name: "native-test", Version: "1"}, nil)
	// The current official client discovers first, then negotiates our supported
	// legacy protocol. Do not hide compatibility errors by pinning the client.
	session, e := client.Connect(ctx, &mcp.IOTransport{Reader: io.NopCloser(reader), Writer: c}, nil)
	if e != nil {
		t.Fatal(e)
	}
	defer session.Close()
	if !strings.Contains(session.InitializeResult().Instructions, "do not wait for the user") {
		t.Fatal("automatic-use initialization instructions missing")
	}
	tools, e := session.ListTools(ctx, nil)
	if e != nil || len(tools.Tools) != 6 {
		t.Fatal(tools, e)
	}
	expectedTools := map[string]bool{"resolve_experience": true, "search_observations": true, "build_evidence_bundle": true, "record_decision": true, "record_observation_use": true, "read_observation_sources": true}
	for _, tool := range tools.Tools {
		if !expectedTools[tool.Name] {
			t.Fatal("unexpected consumer authority", tool.Name)
		}
		if tool.Name == "read_observation_sources" && (tool.Annotations == nil || !tool.Annotations.ReadOnlyHint) {
			t.Fatal("source reader must remain read only")
		}
	}
	query, e := session.CallTool(ctx, &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}}})
	if e != nil || query.IsError {
		t.Fatal(query, e)
	}
	encoded, e := json.Marshal(query.StructuredContent)
	var missingTask map[string]any
	if e != nil || json.Unmarshal(encoded, &missingTask) != nil || missingTask["retrieval"].(map[string]any)["status"] != "TASK_QUERY_REQUIRED" {
		t.Fatal("missing task became an environment recommendation", query, e)
	}
	query, e = session.CallTool(ctx, &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}, "query": "原生队列", "limit": 2, "detail": "summary"}})
	if e != nil || query.IsError {
		t.Fatal("task recall schema/dispatch rejected", query, e)
	}
	encoded, e = json.Marshal(query.StructuredContent)
	var taskResult map[string]any
	if e != nil || json.Unmarshal(encoded, &taskResult) != nil || taskResult["retrieval"].(map[string]any)["method"] != "SQLITE_FTS5_BM25_PUBLIC_NARRATIVES" {
		t.Fatal(taskResult, e)
	}
	observations, e := session.CallTool(ctx, &mcp.CallToolParams{Name: "search_observations", Arguments: map[string]any{"query": "原生队列", "mode": "ranked"}})
	if e != nil || observations.IsError {
		t.Fatal("ranked observation schema/dispatch rejected", observations, e)
	}
	usage := map[string]any{"candidate_id": candidateID, "report_key": "testkey", "purpose": "DEBUGGING", "disposition": "INVESTIGATED", "reason": "Inspected source"}
	invalidUsage := map[string]any{"candidate_id": candidateID, "report_key": "invalidkey", "purpose": "VERIFICATION", "disposition": "INVESTIGATED", "reason": "Inspected source"}
	invalid, e := session.CallTool(ctx, &mcp.CallToolParams{Name: "record_observation_use", Arguments: map[string]any{"report": invalidUsage}})
	if e != nil || !invalid.IsError {
		t.Fatal("invalid report purpose was accepted", invalid, e)
	}
	encodedError, _ := json.Marshal(invalid.Content)
	if !strings.Contains(string(encodedError), "VALIDATION") {
		t.Fatal("invalid report error did not explain allowed values", string(encodedError))
	}
	nullUsage := map[string]any{"candidate_id": candidateID, "report_key": "nullkey", "purpose": "VALIDATION", "disposition": "INVESTIGATED", "reason": "Inspected source", "elapsed_seconds": nil}
	nullResult, e := session.CallTool(ctx, &mcp.CallToolParams{Name: "record_observation_use", Arguments: map[string]any{"report": nullUsage}})
	if e != nil || !nullResult.IsError {
		t.Fatal("explicit null elapsed time was accepted", nullResult, e)
	}
	report, e := session.CallTool(ctx, &mcp.CallToolParams{Name: "record_observation_use", Arguments: map[string]any{"report": usage}})
	if e != nil || report.IsError {
		t.Fatal("usage feedback dispatch rejected", report, e)
	}
	encoded, e = json.Marshal(report.StructuredContent)
	var usageResult map[string]any
	if e != nil || json.Unmarshal(encoded, &usageResult) != nil || usageResult["exposure"] != "NOT_VERIFIED" || usageResult["trusted_outcome"] != "NOT_CREATED" {
		t.Fatal("untrusted usage boundaries lost", usageResult, e)
	}
	for _, tool := range tools.Tools {
		if tool.Name == "review" || tool.Name == "backup" || tool.Name == "source-project" {
			t.Fatal("management leaked into consumer tools")
		}
	}
	response, e = host.ManagementCall(ctx, p, "run-b", "open-run", map[string]any{"public_context": json.RawMessage(`{"worker_count":3.0}`), "enable_proposals": false})
	if e != nil || response["status"] != "FAILED_KNOWN" {
		t.Fatal("Run authority drift accepted", response, e)
	}
	response, e = host.ManagementCall(ctx, p, "run-b", "close-run", map[string]any{})
	if e != nil || response["status"] != "COMPLETED" {
		t.Fatal("explicit revocation failed", response, e)
	}
	response, e = host.ManagementCall(ctx, p, "run-b", "query", map[string]any{"task_context": map[string]any{}})
	if e != nil || response["status"] != "FAILED_KNOWN" {
		t.Fatal("revoked Run accepted work", response, e)
	}
	response, e = host.ManagementCall(ctx, p, "run-b", "open-run", map[string]any{"public_context": json.RawMessage(`{"worker_count":2.0}`), "enable_proposals": false})
	if e != nil || response["status"] != "COMPLETED" {
		t.Fatal("explicit same-facts resume failed", response, e)
	}
	response, e = host.ManagementCall(ctx, p, "run-b", "query", map[string]any{"task_context": map[string]any{}})
	if e != nil || response["status"] != "COMPLETED" {
		t.Fatal("resumed scope unavailable", response, e)
	}
}
