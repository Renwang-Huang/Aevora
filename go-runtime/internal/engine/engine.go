// Package engine is the typed business boundary; it has no MCP dependencies.
package engine

import (
	"context"
	"encoding/json"
	"errors"
)

type RunContext struct {
	BackendID    string          `json:"backend_id"`
	WorkspaceID  string          `json:"workspace_id"`
	RunID        string          `json:"run_id"`
	Facts        json.RawMessage `json:"facts"`
	FactsVersion string          `json:"facts_version"`
	FactsSource  string          `json:"facts_source"`
	Proposals    bool            `json:"enable_proposals"`
}

type Request struct {
	ID             string                      `json:"request_id"`
	Operation      string                      `json:"operation"`
	Arguments      json.RawMessage             `json:"arguments"`
	BeforeDispatch func() error                `json:"-"`
	ValidateResult func(json.RawMessage) error `json:"-"`
}

type Engine interface {
	Health(context.Context) error
	RunBinding() string
	Call(context.Context, RunContext, Request) (json.RawMessage, error)
	Close() error
}

// Manager is a separate trusted Host control plane, never an MCP tool catalog.
type Manager interface {
	Manage(context.Context, Request) (json.RawMessage, error)
}

// MaintenanceReader is an internal Host-only read path. Polling must not mint
// operation receipts or consume external management authentication budgets.
type MaintenanceReader interface {
	ReadMaintenance(context.Context, string, map[string]any) (map[string]any, bool, error)
}

var ErrUnknown = errors.New("AEVORA_OPERATION_UNKNOWN")
var ErrUnavailable = errors.New("AEVORA_GRAPH_UNAVAILABLE")
var ErrInvalid = errors.New("AEVORA_INVALID_OR_UNAUTHORIZED_INPUT")
var ErrRecord = errors.New("AEVORA_GRAPH_RECORD_ERROR")
var ErrNotDispatched = errors.New("AEVORA_OPERATION_NOT_DISPATCHED")
var ErrRunContext = errors.New("AEVORA_RUN_CONTEXT_CONFLICT")
var ErrResultLimit = errors.New("AEVORA_RESULT_BOUND_EXCEEDED")
