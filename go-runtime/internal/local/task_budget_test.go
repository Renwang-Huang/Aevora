package local

import (
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"
)

func TestObservedTaskRecordBudgetCoversBoundedContextAndKeepsOtherRecordsSmall(t *testing.T) {
	root := t.TempDir()
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "registry"))
	p := Project{Schema: "aevora.local-project/1", Name: "budget", Workspace: root, Profile: filepath.Join(root, "host.json"), BackendID: strings.Repeat("a", 64)}
	if err := Register(p); err != nil {
		t.Fatal(err)
	}
	facts := json.RawMessage(`{"target_project":"budget"}`)
	observation, _ := json.Marshal(map[string]any{"schema_version": "aevora.context-observation/1", "facts": facts, "limitations": []string{strings.Repeat("bounded trusted observation ", 220)}})
	if len(observation) <= 4096 {
		t.Fatal("fixture must cover old record ceiling")
	}
	task, err := NewObservedTask(p, "observed", facts, observation, false)
	if err != nil {
		t.Fatal(err)
	}
	loaded, _, err := LoadTask(p.Name, task.Name)
	if err != nil || string(loaded.Context) != string(observation) {
		t.Fatal("observation record truncated or rejected", err)
	}
	if recordLimit(p) != 4096 || recordLimit(TaskState{}) != 4096 {
		t.Fatal("unrelated record limits changed")
	}
	if _, err := NewObservedTask(p, "too-large", facts, json.RawMessage(`{"text":"`+strings.Repeat("x", 65536)+`"}`), false); err == nil {
		t.Fatal("unbounded task accepted")
	}
}
