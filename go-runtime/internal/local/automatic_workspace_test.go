package local

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAutomaticWorkspaceUsesOnlyExplicitPolicyAndStillRejectsRealAmbiguity(t *testing.T) {
	root := t.TempDir()
	os.Chmod(root, 0700)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "registry"))
	nested := filepath.Join(root, "nested")
	os.Mkdir(nested, 0700)
	register := func(name, workspace, backend string) {
		t.Helper()
		if e := Register(Project{Schema: "aevora.local-project/1", Name: name, Workspace: workspace, Profile: filepath.Join(root, "host.json"), BackendID: strings.Repeat(backend, 64)}); e != nil {
			t.Fatal(e)
		}
	}
	register("parent", root, "a")
	register("child", nested, "a")
	register("old-child", nested, "b")
	register("unlisted-child", nested, "a")
	policy := map[string]any{"project": "parent", "workspace": root, "proposals": false, "routes": []any{map[string]any{"project": "child", "workspace": nested}}}
	save := func() {
		raw, _ := json.Marshal(policy)
		if e := os.WriteFile(filepath.Join(root, "automatic-policy.json"), raw, 0600); e != nil {
			t.Fatal(e)
		}
	}
	save()
	if _, e := SelectWorkspace(nested); e == nil {
		t.Fatal("fixture lacks original ambiguity")
	}
	if p, e := SelectAutomaticWorkspace(root, nested); e != nil || p.Name != "child" {
		t.Fatal(p, e)
	}
	policy["routes"] = []any{map[string]any{"project": "child", "workspace": nested}, map[string]any{"project": "unlisted-child", "workspace": nested}}
	save()
	if _, e := SelectAutomaticWorkspace(root, nested); e == nil || e.Error() != "AEVORA_PROJECT_AMBIGUOUS" {
		t.Fatal("authorized ambiguity hidden", e)
	}
	policy["routes"] = []any{}
	save()
	if p, e := SelectAutomaticWorkspace(root, nested); e != nil || p.Name != "parent" {
		t.Fatal("revoked route retained", p, e)
	}
	policy["workspace"] = nested
	save()
	if _, e := SelectAutomaticWorkspace(root, nested); e == nil {
		t.Fatal("changed registration ignored")
	}
}
