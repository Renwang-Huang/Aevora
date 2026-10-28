package native

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestTargetDriftBlocksNewRecallPreservesReplayAndAcceptsFreshTask(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	os.Chmod(root, 0700)
	workspace := filepath.Join(root, "workspace")
	os.Mkdir(workspace, 0700)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "workflow"))
	git := func(args ...string) {
		t.Helper()
		argv := append([]string{"-C", workspace, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false"}, args...)
		cmd := exec.Command("git", argv...)
		cmd.Env = append(os.Environ(), "GIT_CONFIG_GLOBAL="+os.DevNull, "GIT_CONFIG_NOSYSTEM=1")
		if data, e := cmd.CombinedOutput(); e != nil {
			t.Fatal(e, string(data))
		}
	}
	git("init", "-q", "-b", "main")
	os.WriteFile(filepath.Join(workspace, "go.mod"), []byte("module fixture\n\ngo 1.26.0\n"), 0600)
	git("add", "go.mod")
	git("commit", "-qm", "fixture")
	project := local.Project{Schema: "aevora.local-project/1", Name: "target-fixture", Workspace: workspace, Profile: filepath.Join(root, "profile.json"), BackendID: strings.Repeat("b", 64)}
	if err := local.Register(project); err != nil {
		t.Fatal(err)
	}
	observe := func() json.RawMessage {
		t.Helper()
		base, e := observedContext(domain.Map{})
		if e != nil {
			t.Fatal(e)
		}
		value, e := local.ObserveProject(ctx, project, base)
		if e != nil {
			t.Fatal(e)
		}
		raw, e := codec.Canonical(value["facts"])
		if e != nil {
			t.Fatal(e)
		}
		return raw
	}
	scope := engine.RunContext{BackendID: project.BackendID, WorkspaceID: "workspace", RunID: "target-task", Facts: observe(), FactsVersion: "public-context/1", FactsSource: "protected_host_profile"}
	store, e := storage.Open(ctx, filepath.Join(root, "experience.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	runtime, e := New(ctx, store, scope)
	if e != nil {
		store.Close()
		t.Fatal(e)
	}
	defer runtime.Close()
	request := engine.Request{ID: "target-original", Operation: "resolve_experience", Arguments: json.RawMessage(`{"task_context":{},"query":"native queue"}`), BeforeDispatch: func() error { return nil }}
	first, e := runtime.Call(ctx, scope, request)
	if e != nil {
		t.Fatal(e)
	}
	os.WriteFile(filepath.Join(workspace, "go.mod"), []byte("module fixture\n\ngo 1.27.0\n"), 0600)
	changed := request
	changed.ID = "target-changed"
	if _, e = runtime.Call(ctx, scope, changed); !errors.Is(e, engine.ErrRunContext) {
		t.Fatal("new recall used stale target facts", e)
	}
	count, e := store.Read().Count(ctx, "Query", scope.RunID)
	if e != nil || count != 1 {
		t.Fatal("failed recall wrote query", count, e)
	}
	replay, e := runtime.Call(ctx, scope, request)
	if e != nil || string(replay) != string(first) {
		t.Fatal("historical operation replay changed", e)
	}
	next := scope
	next.RunID = "fresh-target-task"
	next.Facts = observe()
	fresh, e := New(ctx, store, next)
	if e != nil {
		t.Fatal(e)
	}
	fresh.shared = true
	defer fresh.Close()
	changed.ID = "target-fresh"
	if _, e = fresh.Call(ctx, next, changed); e != nil {
		t.Fatal("fresh measured task rejected", e)
	}
}
