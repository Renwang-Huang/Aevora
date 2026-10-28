package native

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSummaryFitsActualSDKEncodingWithEscapingAndAuthorizesOnlyReturnedIDs(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	os.Chmod(root, 0700)
	store, e := storage.Open(ctx, filepath.Join(root, "graph.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	scope := engine.RunContext{BackendID: "summary-backend", WorkspaceID: "summary-workspace", RunID: "summary-run", Facts: json.RawMessage(`{}`), FactsVersion: "public-context/1", FactsSource: "protected_host_profile"}
	runtime, e := New(ctx, store, scope)
	if e != nil {
		store.Close()
		t.Fatal(e)
	}
	defer runtime.Close()
	if e = store.Write(ctx, func(r *storage.Repository) error {
		for i := 0; i < 20; i++ {
			if e := r.PutNode(ctx, "Experience", domain.Map{"id": fmt.Sprintf("experience:summary:%02d", i), "title": "queue " + strings.Repeat("<", 600), "public_summary": strings.Repeat("<", 600), "strategy": strings.Repeat("<", 600), "limitations": []any{strings.Repeat("<", 300), strings.Repeat("<", 300)}, "source_type": "synthetic_or_test_fixture"}); e != nil {
				return e
			}
		}
		return nil
	}); e != nil {
		t.Fatal(e)
	}
	encodedSize := 0
	req := engine.Request{ID: "summary-budget", Operation: "resolve_experience", Arguments: json.RawMessage(`{"task_context":{},"query":"queue","limit":20}`), BeforeDispatch: func() error { return nil }, ValidateResult: func(raw json.RawMessage) error {
		// Use the actual official SDK types and serializer, including both text and
		// structured content; canonical byte counts alone cannot cover this.
		body := &mcp.CallToolResult{Meta: mcp.Meta{"operation_id": strings.Repeat("a", 64)}, StructuredContent: raw, Content: []mcp.Content{&mcp.TextContent{Text: string(raw)}}}
		encoded, err := json.Marshal(body)
		if err != nil {
			return err
		}
		encodedSize = len(encoded) + 256
		if encodedSize > wire.MaxMessage {
			return engine.ErrResultLimit
		}
		return nil
	}}
	raw, e := runtime.Call(ctx, scope, req)
	if e != nil {
		t.Fatal("summary caused a full response rollback", e)
	}
	value, e := codec.Parse(raw)
	if e != nil {
		t.Fatal(e)
	}
	out := domain.M(value)
	cards := domain.A(out["candidates"])
	if len(raw) > domain.SummaryBytes || encodedSize > wire.MaxMessage || len(cards) == 0 || len(cards) >= 20 || domain.M(out["retrieval"])["output_truncated"] != true {
		t.Fatal("SDK-aware summary truncation failed", len(raw), encodedSize, len(cards))
	}
	query, e := store.Read().Get(ctx, "Query", domain.S(out["query_id"]))
	if e != nil || len(domain.A(query["candidate_experience_ids"])) != len(cards) {
		t.Fatal("trimmed IDs received query authority", query, e)
	}
}
