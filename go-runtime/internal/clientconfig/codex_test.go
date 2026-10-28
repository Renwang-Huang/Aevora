package clientconfig

import (
	"bytes"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/pelletier/go-toml/v2"
	"os"
	"path/filepath"
	"testing"
)

func TestScopedOverrideAndOwnedEditPreserveUserConfiguration(t *testing.T) {
	b := New("/opt/应用/aevora file", "/private/project space", "task-test")
	var parsed map[string]any
	inline := []byte("value=" + b.Override()[len("mcp_servers.aevora="):])
	if e := toml.Unmarshal(inline, &parsed); e != nil {
		t.Fatal("invalid invocation TOML", e)
	}
	root := t.TempDir()
	home, state := filepath.Join(root, "codex"), filepath.Join(root, "receipt")
	if e := platform.PrivateDir(home, true); e != nil {
		t.Fatal(e)
	}
	original := []byte("# User comment\nmodel='user-choice'\n[mcp_servers.other]\ncommand='existing'\n")
	config := filepath.Join(home, "config.toml")
	if e := platform.Exclusive(config, original); e != nil {
		t.Fatal(e)
	}
	if _, e := Apply(home, state, b, false); e != nil {
		t.Fatal(e)
	}
	first, e := os.ReadFile(config)
	if e != nil || !bytes.HasPrefix(first, original) {
		t.Fatal("user bytes changed", e)
	}
	if _, e = Apply(home, state, b, false); e != nil {
		t.Fatal("idempotent apply failed", e)
	}
	if _, e = Apply(home, state, b, true); e != nil {
		t.Fatal(e)
	}
	back, _ := os.ReadFile(config)
	if !bytes.Equal(back, original) {
		t.Fatal("undo changed unrelated configuration")
	}
	if _, e = Apply(home, state, b, false); e != nil {
		t.Fatal(e)
	}
	changed, _ := os.ReadFile(config)
	changed = append(changed, []byte("[mcp_servers.aevora.tools]\ncustom=true\n")...)
	if e = os.WriteFile(config, changed, 0600); e != nil {
		t.Fatal(e)
	}
	if _, e = Apply(home, state, b, true); e == nil {
		t.Fatal("user-modified entry overwritten")
	}
	preserved, _ := os.ReadFile(config)
	if !bytes.Equal(preserved, changed) {
		t.Fatal("conflict mutated file")
	}
	emptyHome := filepath.Join(root, "empty")
	if e = platform.PrivateDir(emptyHome, true); e != nil {
		t.Fatal(e)
	}
	if e = platform.Exclusive(filepath.Join(emptyHome, "config.toml"), nil); e != nil {
		t.Fatal(e)
	}
	if _, e = Apply(emptyHome, state, b, false); e != nil {
		t.Fatal("empty user configuration rejected", e)
	}
	if _, e = Apply(emptyHome, state, b, true); e != nil {
		t.Fatal("empty configuration undo failed", e)
	}
}

func TestForwardedOverridesCannotRebindTaskMCP(t *testing.T) {
	for _, args := range [][]string{
		{"-c", "mcp_servers.aevora.command='other'"},
		{"--config= mcp_servers . aevora = {}"},
		{"-c", `"mcp_servers".aevora={}`},
		{"-c'mcp_servers'.aevora={}"},
		{"--ignore-user-config"},
	} {
		if !OverridesBinding(args) {
			t.Fatal("fixed binding can be overridden", args)
		}
	}
	for _, args := range [][]string{
		{"-c", "model=chosen-model"},
		{"--config=approval_policy='untrusted'"},
		{"Explain the mcp_servers setting"},
		{"--version"},
	} {
		if OverridesBinding(args) {
			t.Fatal("ordinary user settings or prompt rejected", args)
		}
	}
}
