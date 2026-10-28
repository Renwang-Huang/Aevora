package capture

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRecallEchoExcludesOnlyCompleteMemoryResponses(t *testing.T) {
	cases := []struct {
		value any
		echo  bool
	}{
		{map[string]any{"authority": "UNTRUSTED_OBSERVATIONS_ONLY", "observations": []any{map[string]any{"title": "JSONDecodeError"}}}, true},
		{`{"schema_version":"aevora.cli-response/1","status":"COMPLETED","result":{"authority":"UNTRUSTED_OBSERVATIONS_ONLY","observations":[]}}`, true},
		{`{"query_id":"query:fixture:one","mcp_version":"aevora.mcp/1.1","context_authority":"TRUSTED_PINNED_PUBLIC_FACTS_ONLY","candidates":[]}`, true},
		{`{"authority":"UNTRUSTED_OBSERVATIONS_ONLY","observations":[]}\nconnection refused`, false},
		{map[string]any{"error": "AEVORA_RECONNECT_REQUIRED"}, false},
		{"aevora: permission denied", false},
		{`{"authority":"UNTRUSTED_OBSERVATIONS_ONLY","observations":"invalid","error":"connection refused"}`, false},
	}
	for _, c := range cases {
		if got := memoryEcho(c.value); got != c.echo {
			t.Fatalf("echo=%v want %v for %v", got, c.echo, c.value)
		}
	}
}

func TestProjectNameAndActualAevoraErrorsRemainCaptureable(t *testing.T) {
	root := t.TempDir()
	workspace := filepath.Join(root, "workspace")
	if err := os.Mkdir(workspace, 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "registry"))
	if err := local.Register(local.Project{Schema: "aevora.local-project/1", Name: "fixture", Workspace: workspace, Profile: filepath.Join(root, "host.json"), BackendID: strings.Repeat("a", 64)}); err != nil {
		t.Fatal(err)
	}
	for _, command := range []string{"pytest /tmp/aevora-app/test.py", "aevora query --query x", "printf '%s' aevora | test-network"} {
		input := map[string]any{"hook_event_name": "PostToolUse", "session_id": "session-1", "turn_id": "turn-1", "tool_use_id": "call-1", "cwd": workspace, "tool_name": "Bash", "tool_input": map[string]any{"command": command}, "tool_response": "connection refused"}
		raw, _ := json.Marshal(input)
		event, accepted, err := FromHook(raw)
		if err != nil || !accepted || event.Signal != "CONNECTION_REFUSED" {
			t.Fatal(command, event, accepted, err)
		}
	}
}
