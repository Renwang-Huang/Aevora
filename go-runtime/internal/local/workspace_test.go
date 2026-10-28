package local

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWorkspaceRoutingUsesSpecificOwnedRegistrationAndRejectsAmbiguity(t *testing.T) {
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(t.TempDir(), "registry"))
	root := t.TempDir()
	nested := filepath.Join(root, "nested")
	outside := root + "-other"
	for _, dir := range []string{nested, outside} {
		if err := os.Mkdir(dir, 0700); err != nil {
			t.Fatal(err)
		}
	}
	defer os.Remove(outside)
	register := func(name, dir string) {
		t.Helper()
		if err := Register(Project{Schema: "aevora.local-project/1", Name: name, Workspace: dir, Profile: filepath.Join(dir, "host.json"), BackendID: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}); err != nil {
			t.Fatal(err)
		}
	}
	register("parent", root)
	register("child", nested)
	p, err := SelectWorkspace(nested)
	if err != nil || p.Name != "child" {
		t.Fatal("specific project lost", p, err)
	}
	if _, err = SelectWorkspace(outside); err == nil {
		t.Fatal("string prefix selected parent")
	}
	register("duplicate", nested)
	if _, err = SelectWorkspace(nested); err == nil || err.Error() != "AEVORA_PROJECT_AMBIGUOUS" {
		t.Fatal("ambiguous project selected", err)
	}
	link := filepath.Join(root, "linked")
	if err = os.Symlink(nested, link); err != nil {
		t.Fatal(err)
	}
	if _, err = SelectWorkspace(link); err == nil {
		t.Fatal("symlink evaded ambiguous registration")
	}
}
