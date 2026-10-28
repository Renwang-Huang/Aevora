package taskcapture

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
)

func TestCheckClassificationUnderstandsSimpleInvocationsAndRejectsCompoundResults(t *testing.T) {
	cases := []struct{ command, action string }{
		{"go test ./...", "GO_TEST"},
		{"go -C go-runtime test ./internal/taskcapture", "GO_TEST"},
		{"'/opt/go/bin/go' -C='source dir' test ./...", "GO_TEST"},
		{"python -m pytest tests", "PYTEST"},
		{"/usr/bin/python3.12 -I -m pytest", "PYTEST"},
		{"pytest", "PYTEST"},
		{"npm --prefix console test", "NPM_TEST"},
		{"npm --workspace=web run test", "NPM_TEST"},
		{"/bin/bash -lc 'go -C go-runtime test ./...'", "GO_TEST"},
		{"sh -c 'python -m pytest'", "PYTEST"},
		{"echo 'go test'", "COMMAND"},
		{"go test ./... || true", "COMMAND"},
		{"go test ./...; echo done", "COMMAND"},
		{"go test ./... | cat", "COMMAND"},
		{"! go test ./...", "COMMAND"},
		{"go test ./... &", "COMMAND"},
		{"go test ./... > report", "COMMAND"},
		{"go test $(echo private)", "COMMAND"},
		{"GOFLAGS=-race go test", "COMMAND"},
		{"python -c 'import pytest'", "COMMAND"},
		{"npm --version test", "COMMAND"},
		{"npm --prefix test", "COMMAND"},
		{"go -C", "COMMAND"},
		{"go -C= test", "COMMAND"},
		{"go test 'unterminated", "COMMAND"},
		{"go test " + strings.Repeat("x", 16384), "COMMAND"},
	}
	for _, tc := range cases {
		t.Run(tc.command[:min(len(tc.command), 70)], func(t *testing.T) {
			raw, _ := json.Marshal(domain.Map{"method": "item/completed", "params": domain.Map{"threadId": "thread", "turnId": "turn", "item": domain.Map{"id": "item", "type": "commandExecution", "command": tc.command, "status": "completed", "exitCode": 0, "aggregatedOutput": "private-output-marker"}}})
			event, err := Project(raw, "project", "task")
			if err != nil || event["action"] != tc.action {
				t.Fatalf("got %v, %v; want %s", event, err, tc.action)
			}
			data, _ := json.Marshal(event)
			if strings.Contains(string(data), "private-output-marker") || strings.Contains(string(data), "/opt/go/") {
				t.Fatal("classification leaked source text")
			}
		})
	}
}
