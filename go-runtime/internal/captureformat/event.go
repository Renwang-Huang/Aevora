// Package captureformat defines the small public shape shared by the hook
// producer and the Host receiver. All values are untrusted source claims.
package captureformat

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"regexp"
)

var ErrInvalid = errors.New("AEVORA_CAPTURE_INVALID")
var digest = regexp.MustCompile(`^[a-f0-9]{64}$`)
var project = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`)
var reference = regexp.MustCompile(`^[A-Za-z0-9_-]{1,128}$`)
var credential = regexp.MustCompile(`(?i)(^|[_-])(sk-(?:proj-)?[a-z0-9_-]{16,}|ghp_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,})`)

type Event struct {
	Schema     string `json:"schema_version"`
	ID         string `json:"id"`
	Project    string `json:"project"`
	SourceKey  string `json:"source_key"`
	Tool       string `json:"tool"`
	Signal     string `json:"signal"`
	SessionRef string `json:"session_ref,omitempty"`
	TurnRef    string `json:"turn_ref,omitempty"`
	ToolRef    string `json:"tool_ref,omitempty"`
}

func (e Event) Map() map[string]any {
	return map[string]any{"schema_version": e.Schema, "id": e.ID, "project": e.Project, "source_key": e.SourceKey, "tool": e.Tool, "signal": e.Signal, "session_ref": e.SessionRef, "turn_ref": e.TurnRef, "tool_ref": e.ToolRef}
}
func IsDigest(s string) bool { return digest.MatchString(s) }
func EventID(project, source, tool, signal string) string {
	raw, _ := codec.Canonical([]any{"aevora.codex-signal/1", project, source, tool, signal})
	h := sha256.Sum256(raw)
	return hex.EncodeToString(h[:])
}
func Valid(e Event) bool {
	if e.Schema != "aevora.codex-signal/1" || !IsDigest(e.ID) || !IsDigest(e.SourceKey) || !project.MatchString(e.Project) || credential.MatchString(e.Project) || (e.Tool != "BASH" && e.Tool != "PATCH") {
		return false
	}
	for _, v := range []string{e.SessionRef, e.TurnRef, e.ToolRef} {
		if !reference.MatchString(v) || credential.MatchString(v) {
			return false
		}
	}
	key, err := codec.Digest([]any{e.SessionRef, e.TurnRef, e.ToolRef})
	if err != nil || key != e.SourceKey {
		return false
	}
	switch e.Signal {
	case "JSON_DECODE_ERROR", "RUN_CONTEXT_CONFLICT", "RECONNECT_REQUIRED", "CONNECTION_REFUSED", "PERMISSION_DENIED":
	default:
		return false
	}
	return e.ID == EventID(e.Project, e.SourceKey, e.Tool, e.Signal)
}
func Parse(v map[string]any) (Event, error) {
	if len(v) != 9 {
		return Event{}, ErrInvalid
	}
	get := func(k string) string { x, _ := v[k].(string); return x }
	e := Event{Schema: get("schema_version"), ID: get("id"), Project: get("project"), SourceKey: get("source_key"), Tool: get("tool"), Signal: get("signal"), SessionRef: get("session_ref"), TurnRef: get("turn_ref"), ToolRef: get("tool_ref")}
	if !Valid(e) {
		return Event{}, ErrInvalid
	}
	return e, nil
}

func New(project, session, turn, call, tool, signal string) (Event, error) {
	key, err := codec.Digest([]any{session, turn, call})
	if err != nil {
		return Event{}, ErrInvalid
	}
	e := Event{Schema: "aevora.codex-signal/1", Project: project, SourceKey: key, Tool: tool, Signal: signal, SessionRef: session, TurnRef: turn, ToolRef: call}
	e.ID = EventID(e.Project, e.SourceKey, e.Tool, e.Signal)
	if !Valid(e) {
		return Event{}, ErrInvalid
	}
	return e, nil
}
