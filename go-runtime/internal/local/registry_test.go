package local

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"testing"
)

func TestProjectAndTaskBindingsNeverFollowAmbientSelection(t *testing.T) {
	root := filepath.Join(t.TempDir(), "registry")
	t.Setenv("AEVORA_WORKFLOW_HOME", root)
	workspace := t.TempDir()
	profile := filepath.Join(workspace, "host.json")
	p := Project{Schema: "aevora.local-project/1", Name: "inventory", Workspace: workspace, Profile: profile, BackendID: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
	if e := Register(p); e != nil {
		t.Fatal(e)
	}
	if e := Register(p); e == nil {
		t.Fatal("registration silently replaced")
	}
	got, e := Load(p.Name)
	if e != nil || got != p {
		t.Fatal(got, e)
	}
	task, e := NewTask(p, "first", json.RawMessage(`{"worker_count":1.0}`), false)
	if e != nil {
		t.Fatal(e)
	}
	if e = SetState(task, "AUTHORIZED", ""); e != nil {
		t.Fatal(e)
	}
	if _, e = NewTask(p, "first", json.RawMessage(`{}`), true); e == nil {
		t.Fatal("task binding replaced")
	}
	loaded, state, e := LoadTask(p.Name, "first")
	if e != nil || state.State != "AUTHORIZED" || string(loaded.Facts) != `{"worker_count":1.0}` || loaded.Run != task.Run {
		t.Fatal(loaded, state, e)
	}
	if _, e = ProjectDir("../other"); e == nil {
		t.Fatal("path traversal")
	}
	dir, _ := ProjectDir(p.Name)
	target := filepath.Join(dir, "project.json")
	os.Remove(target)
	if e = os.Symlink(profile, target); e != nil {
		t.Fatal(e)
	}
	if _, e = Load(p.Name); e == nil {
		t.Fatal("linked project accepted")
	}
	if e = platform.PrivateDir(root, false); e != nil {
		t.Fatal(e)
	}
}

func TestMissingLookupsDoNotCreateEntriesOrBreakTaskList(t *testing.T) {
	root := filepath.Join(t.TempDir(), "registry")
	t.Setenv("AEVORA_WORKFLOW_HOME", root)
	workspace := t.TempDir()
	p := Project{Schema: "aevora.local-project/1", Name: "example", Workspace: workspace, Profile: filepath.Join(workspace, "host.json"), BackendID: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
	if err := Register(p); err != nil {
		t.Fatal(err)
	}
	if _, err := NewTask(p, "actual", json.RawMessage(`{}`), false); err != nil {
		t.Fatal(err)
	}
	if _, _, err := LoadTask(p.Name, "missing"); err == nil || err.Error() != "AEVORA_TASK_NOT_FOUND" {
		t.Fatal("missing task was accepted", err)
	}
	if _, err := os.Lstat(filepath.Join(root, "projects", p.Name, "tasks", "missing")); !os.IsNotExist(err) {
		t.Fatal("lookup created task directory", err)
	}
	if _, err := Load("absent"); !os.IsNotExist(err) {
		t.Fatal("missing project was accepted", err)
	}
	if _, err := os.Lstat(filepath.Join(root, "projects", "absent")); !os.IsNotExist(err) {
		t.Fatal("lookup created project directory", err)
	}
	if tasks, err := Tasks(p.Name); err != nil || len(tasks) != 1 {
		t.Fatal("missing lookup broke listing", tasks, err)
	}
}
