package capture

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

func TestHookOutboxIsSanitizedDurableAndAcknowledgedExactly(t *testing.T) {
	root := t.TempDir()
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "registry"))
	workspace := filepath.Join(root, "workspace")
	if err := os.Mkdir(workspace, 0700); err != nil {
		t.Fatal(err)
	}
	if err := local.Register(local.Project{Schema: "aevora.local-project/1", Name: "fixture", Workspace: workspace, Profile: filepath.Join(root, "profile.json"), BackendID: strings.Repeat("a", 64)}); err != nil {
		t.Fatal(err)
	}
	sessionRoot := filepath.Join(root, "sessions")
	if err := platform.PrivateDir(sessionRoot, true); err != nil {
		t.Fatal(err)
	}
	input := map[string]any{"hook_event_name": "PostToolUse", "session_id": "session-1", "turn_id": "turn-1", "tool_use_id": "call-1", "cwd": workspace, "tool_name": "Bash", "tool_input": map[string]any{"command": "python -m pytest"}, "tool_response": map[string]any{"output": "JSONDecodeError SECRET_TEST_MARKER /private/sensitive-marker"}, "transcript_path": "/private/sensitive-marker"}
	raw, _ := json.Marshal(input)
	e, accepted, err := FromHook(raw)
	if err != nil || !accepted || e.Signal != "JSON_DECODE_ERROR" || e.Project != "fixture" {
		t.Fatal(e, accepted, err)
	}
	first, err := Enqueue(sessionRoot, e)
	if err != nil || !first {
		t.Fatal(first, err)
	}
	var wg sync.WaitGroup
	errs := make(chan error, 16)
	for range 16 {
		wg.Add(1)
		go func() { defer wg.Done(); _, e2 := Enqueue(sessionRoot, e); errs <- e2 }()
	}
	wg.Wait()
	close(errs)
	for e2 := range errs {
		if e2 != nil {
			t.Fatal(e2)
		}
	}
	pending, err := Pending(sessionRoot, 20)
	if err != nil || len(pending) != 1 || pending[0] != e {
		t.Fatal(pending, err)
	}
	path := filepath.Join(sessionRoot, "capture-outbox", e.ID+".json")
	stored, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, secret := range []string{"SECRET_TEST_MARKER", "sensitive-marker", workspace, "python -m pytest"} {
		if strings.Contains(string(stored), secret) {
			t.Fatal("raw hook content entered outbox")
		}
	}
	if e.SessionRef != "session-1" || e.TurnRef != "turn-1" || e.ToolRef != "call-1" {
		t.Fatal("source locator missing", e)
	}
	if _, err := captureformat.New("fixture", "sk-proj-aaaaaaaaaaaaaaaaaaaa", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR"); err == nil {
		t.Fatal("credential-shaped source identity accepted")
	}
	if err = Acknowledge(sessionRoot, e, strings.Repeat("0", 64)); err == nil {
		t.Fatal("wrong receipt acknowledged")
	}
	if _, err = os.Stat(path); err != nil {
		t.Fatal("unacknowledged event lost", err)
	}
	receipt, _ := codec.Digest(e.Map())
	if err = Acknowledge(sessionRoot, e, receipt); err != nil {
		t.Fatal(err)
	}
	pending, err = Pending(sessionRoot, 20)
	if err != nil || len(pending) != 0 {
		t.Fatal(pending, err)
	}
	input["tool_input"] = map[string]any{"command": "aevora observations --query x"}
	input["tool_response"] = map[string]any{"authority": "UNTRUSTED_OBSERVATIONS_ONLY", "observations": []any{map[string]any{"title": "JSONDecodeError"}}}
	raw, _ = json.Marshal(input)
	if _, ok, err := FromHook(raw); err != nil || ok {
		t.Fatal("memory echo was captured", ok, err)
	}
	input["tool_input"] = map[string]any{"command": "python -m pytest"}
	input["tool_response"] = "JSONDecodeError"
	input["cwd"] = root
	raw, _ = json.Marshal(input)
	if _, ok, err := FromHook(raw); err != nil || ok {
		t.Fatal("unregistered project captured", ok, err)
	}
}

func TestRootScopedHookClassificationIgnoresUnlistedRestoredAliases(t *testing.T) {
	root := t.TempDir()
	os.Chmod(root, 0700)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "registry"))
	for _, name := range []string{"old", "current"} {
		if e := local.Register(local.Project{Schema: "aevora.local-project/1", Name: name, Workspace: root, Profile: filepath.Join(root, "host.json"), BackendID: strings.Repeat("a", 64)}); e != nil {
			t.Fatal(e)
		}
	}
	policy, _ := json.Marshal(map[string]any{"project": "current", "workspace": root, "proposals": false})
	os.WriteFile(filepath.Join(root, "automatic-policy.json"), policy, 0600)
	raw, _ := json.Marshal(map[string]any{"hook_event_name": "PostToolUse", "session_id": "test-session", "turn_id": "test-turn", "tool_use_id": "test-call", "cwd": root, "tool_name": "Bash", "tool_input": map[string]any{"command": "public-fixture-check"}, "tool_response": "JSONDecodeError"})
	e, reason, err := ClassifyHookForRoot(root, raw)
	if err != nil || reason != "SIGNAL" || e.Project != "current" {
		t.Fatal(e, reason, err)
	}
	os.WriteFile(filepath.Join(root, "automatic-policy.json"), []byte(`{"invalid":true}`), 0600)
	if _, _, err = ClassifyHookForRoot(root, raw); err == nil {
		t.Fatal("invalid policy fell back to global registry")
	}
}

func TestOutboxRejectsTamperedRecordAndUnsafeDirectory(t *testing.T) {
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	e, err := captureformat.New("fixture", "session-1", "turn-1", "call-1", "BASH", "PERMISSION_DENIED")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Enqueue(root, e); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "capture-outbox", e.ID+".json")
	if err := os.WriteFile(path, []byte(`{"unsafe":"marker"}`), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := Pending(root, 10); err == nil {
		t.Fatal("tampered event accepted")
	}
	otherEvent, err := captureformat.New("fixture", "session-1", "turn-1", "call-2", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Enqueue(root, otherEvent); err != nil {
		t.Fatal(err)
	}
	scan, err := Scan(root, 10)
	if err != nil || scan.Invalid != 1 || len(scan.Events) != 1 || scan.Events[0] != otherEvent {
		t.Fatal("corrupt event blocked valid work", scan, err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatal("tampered event erased")
	}
	other := filepath.Join(t.TempDir(), "linked-root")
	if err := os.Symlink(root, other); err != nil {
		t.Fatal(err)
	}
	if _, err := Enqueue(other, e); err == nil {
		t.Fatal("linked root accepted")
	}
}
