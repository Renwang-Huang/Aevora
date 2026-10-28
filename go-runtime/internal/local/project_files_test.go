package local

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestProjectDirtyStateManifestRequirementsAndMetadataChanges(t *testing.T) {
	root := t.TempDir()
	git := func(args ...string) {
		t.Helper()
		argv := append([]string{"-C", root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false"}, args...)
		cmd := exec.Command("git", argv...)
		cmd.Env = append(os.Environ(), "GIT_CONFIG_GLOBAL="+os.DevNull, "GIT_CONFIG_NOSYSTEM=1")
		if data, e := cmd.CombinedOutput(); e != nil {
			t.Fatal(e, string(data))
		}
	}
	git("init", "-q", "-b", "main")
	files := map[string]string{"go.mod": "module example.invalid/fixture\n\ngo 1.26.0\n", "package.json": `{"engines":{"node":">=20"},"private_note":"never-copy-this"}`, "pyproject.toml": "[project]\nrequires-python = \">=3.12,<3.13\"\n", "code.go": "package fixture\n"}
	for name, data := range files {
		if e := os.WriteFile(filepath.Join(root, name), []byte(data), 0600); e != nil {
			t.Fatal(e)
		}
	}
	git("add", ".")
	git("commit", "-qm", "fixture")
	base := domain.Map{"source": "TRUSTED_NATIVE_RUNTIME_OBSERVATION", "facts": domain.Map{}, "facts_sha256": domain.H(domain.Map{}), "fact_sources": domain.Map{}}
	project := Project{Name: "fixture", Workspace: root}
	observe := func() domain.Map {
		t.Helper()
		v, e := ObserveProject(context.Background(), project, base)
		if e != nil {
			t.Fatal(e)
		}
		return v
	}
	clean := observe()
	facts := domain.M(clean["facts"])
	expected := domain.Map{"target_worktree_state": "CLEAN", "target_go_requirement": "1.26.0", "target_node_requirement": ">=20", "target_python_requirement": ">=3.12,<3.13", "target_manifest_set": "go+npm+python"}
	for key, value := range expected {
		if facts[key] != value {
			t.Fatal(key, clean)
		}
	}
	first := facts["target_worktree_snapshot"]
	os.WriteFile(filepath.Join(root, "code.go"), []byte("package fixture\n// edit one\n"), 0600)
	dirty := domain.M(observe()["facts"])
	if dirty["target_worktree_state"] != "DIRTY" || dirty["target_worktree_snapshot"] == first {
		t.Fatal("first edit invisible", dirty)
	}
	os.WriteFile(filepath.Join(root, "code.go"), []byte("package fixture\n// edit two, changed again\n"), 0600)
	again := domain.M(observe()["facts"])
	if again["target_worktree_snapshot"] == dirty["target_worktree_snapshot"] {
		t.Fatal("same dirty status masked later edit")
	}
	git("add", "code.go")
	staged := domain.M(observe()["facts"])
	if staged["target_worktree_snapshot"] == again["target_worktree_snapshot"] {
		t.Fatal("index change invisible")
	}
	os.WriteFile(filepath.Join(root, "go.mod"), []byte("module example.invalid/fixture\n\ngo 1.27.0\n"), 0600)
	changed := observe()
	if domain.M(changed["facts"])["target_dependency_snapshot"] == facts["target_dependency_snapshot"] {
		t.Fatal("dependency content change invisible")
	}
	raw, _ := codec.Canonical(changed)
	if strings.Contains(string(raw), root) || strings.Contains(string(raw), "never-copy-this") || strings.Contains(string(raw), "fixture@example") {
		t.Fatal("project-private material leaked")
	}
	child := filepath.Join(root, "child")
	os.Mkdir(child, 0700)
	project.Workspace = child
	nested := observe()
	if domain.FactState(domain.M(nested["facts"]), "target_revision") == "KNOWN" {
		t.Fatal("unversioned project inherited parent HEAD")
	}
	project.Workspace = root
	os.Remove(filepath.Join(root, "package.json"))
	if e := os.Symlink(filepath.Join(t.TempDir(), "not-public"), filepath.Join(root, "package.json")); e != nil {
		t.Fatal(e)
	}
	bounded := observe()
	if domain.M(bounded["target_observation"])["manifest_status"] != "UNAVAILABLE_OR_LIMITED" || domain.M(bounded["facts"])["target_dependency_snapshot"] != nil {
		t.Fatal("symlink manifest treated as measured", bounded)
	}
	if e := os.WriteFile(filepath.Join(root, string([]byte{0xff})), []byte("fixture"), 0600); e != nil {
		t.Fatal(e)
	}
	invalidName := observe()
	if domain.M(invalidName["facts"])["target_worktree_snapshot"] != nil || domain.M(invalidName["target_observation"])["worktree_status"] != "UNAVAILABLE_OR_LIMITED" {
		t.Fatal("invalid filename became a trusted snapshot", invalidName)
	}
}
