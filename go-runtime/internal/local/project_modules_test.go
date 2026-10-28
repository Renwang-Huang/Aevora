package local

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestManifestObservationCoversImmediateModulesAndKeepsConflictsUnknown(t *testing.T) {
	root := t.TempDir()
	write := func(name, data string) {
		t.Helper()
		p := filepath.Join(root, name)
		if e := os.MkdirAll(filepath.Dir(p), 0700); e != nil {
			t.Fatal(e)
		}
		if e := os.WriteFile(p, []byte(data), 0600); e != nil {
			t.Fatal(e)
		}
	}
	write("pyproject.toml", "[project]\nrequires-python = \">=3.12,<3.13\"\n")
	write("runtime/go.mod", "module example.invalid/fixture\n\ngo 1.26.0\n")
	write("console/package.json", `{"engines":{"node":">=20"}}`)
	write("node_modules/vendor/go.mod", "module ignored\ngo 9.99\n")
	write(".venv/pyproject.toml", "[project]\nrequires-python = \">=9\"\n")
	facts, status := observeManifests(root)
	expected := map[string]any{"target_manifest_set": "go+npm+python", "target_go_requirement": "1.26.0", "target_node_requirement": ">=20", "target_python_requirement": ">=3.12,<3.13"}
	for key, value := range expected {
		if facts[key] != value {
			t.Fatal("immediate modules missed", key, facts, status)
		}
	}
	first := facts["target_dependency_snapshot"]
	write("runtime/go.sum", "example.invalid/dependency v1.0.0 h1:fixture\n")
	changed, _ := observeManifests(root)
	if changed["target_dependency_snapshot"] == first {
		t.Fatal("module lockfile change invisible")
	}
	write("other/go.mod", "module other\n\ngo 1.25.0\n")
	mixed, status := observeManifests(root)
	if mixed["target_go_requirement"] != nil || mixed["target_manifest_set"] != "go+npm+python" || !strings.Contains(status, "MULTIPLE_REQUIREMENTS_UNKNOWN") {
		t.Fatal("picked one conflicting module requirement", mixed, status)
	}
}

func TestManifestModuleProbeDoesNotFollowSymlinkDirectories(t *testing.T) {
	root, outside := t.TempDir(), t.TempDir()
	if e := os.WriteFile(filepath.Join(outside, "go.mod"), []byte("module outside\n\ngo 1.99.0\n"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.Symlink(outside, filepath.Join(root, "linked")); e != nil {
		t.Fatal(e)
	}
	facts, status := observeManifests(root)
	if facts["target_go_requirement"] != nil || facts["target_dependency_snapshot"] == nil || status != "REGISTERED_ROOT_AND_IMMEDIATE_MODULES" {
		t.Fatal("followed outside module", facts)
	}
}

func TestManifestDiscoveryLimitDisclosesRootOnlyCoverage(t *testing.T) {
	root := t.TempDir()
	if e := os.WriteFile(filepath.Join(root, "go.mod"), []byte("module root\n\ngo 1.26.0\n"), 0600); e != nil {
		t.Fatal(e)
	}
	for i := 0; i < 257; i++ {
		f, e := os.CreateTemp(root, "fixture-")
		if e != nil {
			t.Fatal(e)
		}
		f.Close()
	}
	facts, status := observeManifests(root)
	if facts["target_go_requirement"] != "1.26.0" || status != "ROOT_ONLY_CHILD_ENTRY_LIMIT" {
		t.Fatal("discovery limit discarded roots or hid coverage", facts, status)
	}
}
