package host

import (
	"bytes"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// toolResult uses the official SDK's actual serializer, including the complete
// structured result and serialized-JSON text fallback. RawMessage preserves
// canonical numeric identity; generic schema round trips through float64 do not.
func toolResult(id string, raw json.RawMessage) (*mcp.CallToolResult, error) {
	if _, e := wire.Decode(raw, wire.MaxMessage); e != nil {
		return nil, engine.ErrResultLimit
	}
	value := &mcp.CallToolResult{Meta: mcp.Meta{"operation_id": id}, StructuredContent: raw, Content: []mcp.Content{&mcp.TextContent{Text: string(raw)}}}
	encoded, e := json.Marshal(value)
	if e != nil {
		return nil, engine.ErrResultLimit
	}
	// The input gate caps the encoded JSON-RPC id at 130 bytes. Reserve 256
	// bytes for that id, envelope keys and newline, without changing frame limits.
	if len(encoded)+256 > wire.MaxMessage {
		return nil, engine.ErrResultLimit
	}
	// Validate depth and node limits after adding the real protocol nesting.
	frame := append([]byte(`{"jsonrpc":"2.0","id":"`+string(bytes.Repeat([]byte("i"), 128))+`","result":`), encoded...)
	frame = append(frame, '}', '\n')
	if _, e = wire.Decode(frame, wire.MaxMessage); e != nil {
		return nil, engine.ErrResultLimit
	}
	return value, nil
}
func managementResultBudget(id string, raw json.RawMessage) error {
	if _, e := wire.Decode(raw, wire.MaxMessage); e != nil {
		return engine.ErrResultLimit
	}
	encoded, e := json.Marshal(map[string]any{"status": "COMPLETED", "operation_id": id, "result": raw})
	if e != nil || len(encoded) > wire.MaxMessage {
		return engine.ErrResultLimit
	}
	if _, e = wire.Decode(encoded, wire.MaxMessage); e != nil {
		return engine.ErrResultLimit
	}
	return nil
}
