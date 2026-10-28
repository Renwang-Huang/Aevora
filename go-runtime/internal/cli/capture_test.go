package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/capture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCaptureHookNeverBlocksToolResultAndKeepsInputPrivate(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(dir, "registry"))
	workspace := filepath.Join(dir, "workspace")
	if err := os.Mkdir(workspace, 0700); err != nil {
		t.Fatal(err)
	}
	if err := local.Register(local.Project{Schema: "aevora.local-project/1", Name: "fixture", Workspace: workspace, Profile: filepath.Join(dir, "host.json"), BackendID: strings.Repeat("a", 64)}); err != nil {
		t.Fatal(err)
	}
	root := filepath.Join(dir, "sessions")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	value := map[string]any{"hook_event_name": "PostToolUse", "session_id": "session-1", "turn_id": "turn-1", "tool_use_id": "call-1", "cwd": workspace, "tool_name": "Bash", "tool_input": map[string]any{"command": "pytest"}, "tool_response": "JSONDecodeError SECRET_TEST_MARKER"}
	raw, _ := json.Marshal(value)
	var out, stderr bytes.Buffer
	code := Execute(context.Background(), []string{"capture", "hook", "--session-root", root}, bytes.NewReader(raw), &out, &stderr, native.Factory())
	if code != 0 || out.String() != "{}\n" || stderr.Len() != 0 {
		t.Fatal(code, out.String(), stderr.String())
	}
	scan, err := capture.Scan(root, 10)
	if err != nil || scan.Pending != 1 {
		t.Fatal(scan, err)
	}
	callback, err := capture.ReadCallback(root)
	if err != nil || callback["reason"] != "QUEUED" {
		t.Fatal(callback, err)
	}
	out.Reset()
	stderr.Reset()
	bad := strings.Repeat("SECRET_TEST_MARKER", capture.MaxInput/4)
	code = Execute(context.Background(), []string{"capture", "hook", "--session-root", root}, strings.NewReader(bad), &out, &stderr, native.Factory())
	if code != 0 || !strings.Contains(out.String(), "AEVORA_CAPTURE_INVALID") || strings.Contains(out.String(), "SECRET_TEST_MARKER") || stderr.Len() != 0 {
		t.Fatal("hook error interfered with tool", code, out.String(), stderr.String())
	}
	callback, err = capture.ReadCallback(root)
	if err != nil || callback["reason"] != "INVALID_INPUT" {
		t.Fatal(callback, err)
	}
}
