package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/upgrade"
)

func TestProjectRecoveryPreservesChangedBindingAndRequiresFreshAuthority(t *testing.T) {
	root := t.TempDir()
	os.Chmod(root, 0700)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "workflow"))
	t.Setenv("XDG_STATE_HOME", filepath.Join(root, "state"))
	ctx := context.Background()
	run := func(args ...string) ([]byte, error) {
		c := Command(native.Factory())
		var out bytes.Buffer
		c.SetArgs(args)
		c.SetOut(&out)
		c.SetErr(&bytes.Buffer{})
		err := c.ExecuteContext(ctx)
		return out.Bytes(), err
	}
	if _, e := run("project", "init", "--name", "original", "--workspace", root); e != nil {
		t.Fatal(e)
	}
	pr, p, e := selectedProject("original")
	if e != nil {
		t.Fatal(e)
	}
	oldTask, e := local.NewTask(pr, "previous-authority", json.RawMessage(`{}`), true)
	if e != nil {
		t.Fatal(e)
	}
	if e = local.SetState(oldTask, "AUTHORIZED", ""); e != nil {
		t.Fatal(e)
	}
	backup := filepath.Join(root, "backup.sqlite")
	if _, e = run("backup", "--config", pr.Profile, "--output", backup); e != nil {
		t.Fatal(e)
	}
	pin, e := upgrade.Digest(backup)
	if e != nil {
		t.Fatal(e)
	}
	// An enrolled backend mismatch must not prevent diagnosis/recovery, and
	// ordinary business calls must still reject it.
	binding := filepath.Join(local.Home(), "projects", "original", "project.json")
	pr.BackendID = strings.Repeat("a", 64)
	raw, _ := json.Marshal(pr)
	if e = os.WriteFile(binding, raw, 0600); e != nil {
		t.Fatal(e)
	}
	if _, _, e = selectedProject(pr.Name); e == nil || e.Error() != "AEVORA_PROJECT_BACKEND_CHANGED" {
		t.Fatal(e)
	}
	out, e := run("project", "inspect", "--project", "original", "--json")
	if e != nil || !bytes.Contains(out, []byte(`"state":"BACKEND_CHANGED"`)) {
		t.Fatal(string(out), e)
	}
	if _, e = run("project", "recover", "--name", "original", "--as", "badpin", "--backup", backup, "--sha256", strings.Repeat("0", 64)); e == nil {
		t.Fatal("bad pin accepted")
	}
	if all, e := local.Projects(); e != nil || len(all) != 1 {
		t.Fatal("failed import poisoned registry", all, e)
	}
	out, e = run("project", "recover", "--project", "original", "--as", "recovered", "--backup", backup, "--sha256", pin, "--json")
	if e != nil {
		t.Fatal(string(out), e)
	}
	next, np, e := selectedProject("recovered")
	if e != nil || next.BackendID == pr.BackendID || np.Session.Root == p.Session.Root || string(np.Session.Facts) != "{}" {
		t.Fatal(next, np, e)
	}
	if tasks, e := local.Tasks(next.Name); e != nil || len(tasks) != 0 {
		t.Fatal("old tasks inherited", tasks, e)
	}
	if _, state, e := local.LoadTask(pr.Name, oldTask.Name); e != nil || state.State != "AUTHORIZED" {
		t.Fatal("source task state was rewritten", state, e)
	}
	after, e := os.ReadFile(binding)
	if e != nil || !bytes.Equal(after, raw) {
		t.Fatal("old binding changed", e)
	}
	if digest, e := upgrade.Digest(backup); e != nil || digest != pin {
		t.Fatal("backup modified", e)
	}
	if _, e = run("project", "recover", "--name", "original", "--as", "recovered", "--backup", backup, "--sha256", pin); e == nil {
		t.Fatal("existing alias replaced")
	}
	if _, e = run("project", "inspect", "--name", "original", "--project", "recovered"); e == nil {
		t.Fatal("conflicting selectors accepted")
	}
	if e = os.Rename(p.Database.Path, p.Database.Path+".retained"); e != nil {
		t.Fatal(e)
	}
	if _, _, e = selectedProject("original"); e == nil || e.Error() != "AEVORA_PROJECT_BACKEND_UNAVAILABLE" {
		t.Fatal("unavailable classified as changed", e)
	}
	out, e = run("project", "inspect", "--name", "original", "--json")
	if e != nil || !bytes.Contains(out, []byte(`"state":"BACKEND_UNAVAILABLE"`)) {
		t.Fatal(string(out), e)
	}
}
