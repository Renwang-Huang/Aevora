package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/taskcapture"
)

func TestLocalCheckPreservesProcessResultAndCapturesOnlyPublicMetadata(t *testing.T) {
	for _, tc := range []struct {
		name        string
		code        int
		brokenQueue bool
	}{
		{"success", 0, false}, {"failure", 7, false},
		{"capture-fails-with-success", 0, true}, {"capture-fails-with-failure", 9, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root, workspace, sessions := checkFixture(t)
			check := filepath.Join(root, "go")
			// Real child, real cwd/stdin/stdout/stderr/exit. No model or private evaluator.
			body := "#!/bin/sh\n[ \"$PWD\" = \"$EXPECTED_CHECK_CWD\" ] || exit 41\nread value\nprintf '%s' \"$value\"\nprintf 'private-stderr-marker' >&2\nexit " + strconv.Itoa(tc.code) + "\n"
			if err := os.WriteFile(check, []byte(body), 0700); err != nil {
				t.Fatal(err)
			}
			t.Setenv("EXPECTED_CHECK_CWD", workspace)
			if tc.brokenQueue {
				if err := os.WriteFile(filepath.Join(sessions, "task-outbox"), []byte("retained conflict"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			var out, stderr bytes.Buffer
			code := Execute(context.Background(), []string{"--project", "fixture", "memory", "run-check", "--task", "capture-repair", "--", check, "-C", "module", "test", "private-argument-marker"}, strings.NewReader("private-stdin-marker\n"), &out, &stderr, native.Factory())
			if code != tc.code || out.String() != "private-stdin-marker" || !strings.HasPrefix(stderr.String(), "private-stderr-marker") {
				t.Fatal(code, out.String(), stderr.String())
			}
			status := taskcapture.Status(sessions)
			if domain.M(status["local_check"])["project"] != "fixture" || domain.M(domain.A(status["clients"])[0])["state"] != "NOT_OBSERVED" {
				t.Fatal("explicit check must not impersonate official client coverage", status)
			}
			if tc.brokenQueue {
				if !strings.Contains(stderr.String(), "CAPTURE_FAILED") {
					t.Fatal(stderr.String())
				}
				return
			}
			pending, _, err := taskcapture.Scan(sessions, 10)
			if err != nil || len(pending) != 1 {
				t.Fatal(pending, err)
			}
			event := pending[0].Event
			if event["action"] != "GO_TEST" || event["kind"] != "CHECK" || event["occurred_at"] == nil || event["revision"] != nil {
				t.Fatal(event)
			}
			if (event["status"] == "COMPLETED") != (tc.code == 0) || domain.I(event["exit_code"]) != tc.code {
				t.Fatal(event)
			}
			data, _ := os.ReadFile(pending[0].Path)
			if strings.Contains(string(data), "private-") || strings.Contains(string(data), workspace) || strings.Contains(string(data), check) {
				t.Fatal("local check persisted private process content")
			}
		})
	}
}

func TestLocalCheckRejectsUnknownCommandsOrInvalidLabelsBeforeStarting(t *testing.T) {
	root, _, sessions := checkFixture(t)
	check := filepath.Join(root, "go")
	marker := filepath.Join(root, "started")
	os.WriteFile(check, []byte("#!/bin/sh\ntouch '"+marker+"'\n"), 0700)
	for _, args := range [][]string{
		{"--task", "bad/path", "--", check, "test"},
		{"--task", "ok", "--", "/bin/sh", "-c", check + " test"},
		{"--task", "ok", check, "test"},
	} {
		var out, stderr bytes.Buffer
		code := Execute(context.Background(), append([]string{"--project", "fixture", "memory", "run-check"}, args...), strings.NewReader(""), &out, &stderr, native.Factory())
		if code == 0 {
			t.Fatal(args, out.String(), stderr.String())
		}
		if _, err := os.Stat(marker); !os.IsNotExist(err) {
			t.Fatal("invalid check ran", args, err)
		}
	}
	if rows, _, err := taskcapture.Scan(sessions, 10); err != nil || len(rows) != 0 {
		t.Fatal(rows, err)
	}
}

func TestLocalCheckUnknownStartFailureDoesNotInventFailedTest(t *testing.T) {
	root, _, sessions := checkFixture(t)
	var out, stderr bytes.Buffer
	code := Execute(context.Background(), []string{"--project", "fixture", "memory", "run-check", "--task", "repair", "--", filepath.Join(root, "missing", "go"), "test"}, strings.NewReader(""), &out, &stderr, native.Factory())
	rows, _, err := taskcapture.Scan(sessions, 10)
	if code != 2 || err != nil || len(rows) != 1 || rows[0].Event["status"] != "UNKNOWN" || rows[0].Event["exit_code"] != nil {
		t.Fatal(code, rows, err, stderr.String())
	}
}

func TestLocalCheckCancellationRemainsUnknown(t *testing.T) {
	root, _, sessions := checkFixture(t)
	check := filepath.Join(root, "go")
	if err := os.WriteFile(check, []byte("#!/bin/sh\nexec sleep 30\n"), 0700); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 150*time.Millisecond)
	defer cancel()
	var out, stderr bytes.Buffer
	code := Execute(ctx, []string{"--project", "fixture", "memory", "run-check", "--task", "repair", "--", check, "test"}, strings.NewReader(""), &out, &stderr, native.Factory())
	rows, _, err := taskcapture.Scan(sessions, 10)
	if code != 130 || err != nil || len(rows) != 1 || rows[0].Event["status"] != "UNKNOWN" || rows[0].Event["exit_code"] != nil {
		t.Fatal(code, rows, err, stderr.String())
	}
}

func checkFixture(t *testing.T) (string, string, string) {
	t.Helper()
	root := t.TempDir()
	os.Chmod(root, 0700)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "workflow"))
	workspace, sessions := filepath.Join(root, "workspace"), filepath.Join(root, "sessions")
	os.Mkdir(workspace, 0700)
	os.Mkdir(sessions, 0700)
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind, p.Database.Path = "sqlite", filepath.Join(root, "graph.sqlite")
	store, err := storage.Open(context.Background(), p.Database.Path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	if err = store.Close(); err != nil {
		t.Fatal(err)
	}
	p.Session.Root, p.Session.Facts = sessions, json.RawMessage(`{}`)
	p.Console.Port = 17805
	raw, _ := json.Marshal(p)
	profile := filepath.Join(root, "host.json")
	os.WriteFile(profile, raw, 0600)
	if err := local.Register(local.Project{Schema: "aevora.local-project/1", Name: "fixture", Workspace: workspace, Profile: profile, BackendID: host.BackendID(p)}); err != nil {
		t.Fatal(err)
	}
	return root, workspace, sessions
}
