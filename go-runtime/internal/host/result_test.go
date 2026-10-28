package host

import (
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"strings"
	"testing"
)

func TestToolResultPreservesNumbersAndBudgetsActualSDKEncoding(t *testing.T) {
	raw := json.RawMessage(`{"float":1.0,"integer":9007199254740993,"negative_zero":-0.0}`)
	value, e := toolResult(strings.Repeat("a", 64), raw)
	if e != nil {
		t.Fatal(e)
	}
	encoded, e := json.Marshal(value)
	if e != nil {
		t.Fatal(e)
	}
	var envelope struct {
		Structured json.RawMessage `json:"structuredContent"`
		Content    []struct {
			Text string `json:"text"`
		} `json:"content"`
	}
	if e = json.Unmarshal(encoded, &envelope); e != nil {
		t.Fatal(e)
	}
	if string(envelope.Structured) != string(raw) || len(envelope.Content) != 1 || envelope.Content[0].Text != string(raw) {
		t.Fatal("SDK encoding changed canonical numeric identity", string(encoded))
	}
	// A valid full response above the former 64 KiB pre-limit fits the wire.
	fitting := json.RawMessage(`{"evidence":"` + strings.Repeat("x", 85000) + `"}`)
	if _, e = toolResult(strings.Repeat("a", 64), fitting); e != nil {
		t.Fatal("valid full result rejected", e)
	}
	// HTML escaping expands both SDK representations; raw byte size alone is unsafe.
	amplified := json.RawMessage(`{"evidence":"` + strings.Repeat("<", 30000) + `"}`)
	if len(amplified) >= 65536 {
		t.Fatal("bad test fixture")
	}
	if _, e = toolResult(strings.Repeat("a", 64), amplified); !errors.Is(e, engine.ErrResultLimit) {
		t.Fatal("SDK expansion crossed the frame limit", e)
	}
	frame, e := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": strings.Repeat("i", 128), "result": value})
	if e != nil || len(frame)+1 > wire.MaxMessage {
		t.Fatal("budget did not cover JSON-RPC envelope", e)
	}
}
