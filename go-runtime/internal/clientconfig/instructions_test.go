package clientconfig

import (
	"bytes"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"testing"
)

func TestAutomaticInstructionsPreserveUserTextAndRefuseModifiedBlock(t *testing.T) {
	home, state := filepath.Join(t.TempDir(), "codex"), filepath.Join(t.TempDir(), "state")
	if err := platform.PrivateDir(home, true); err != nil {
		t.Fatal(err)
	}
	original := []byte("用户原有指令保持原样。\n")
	path := filepath.Join(home, "AGENTS.md")
	os.WriteFile(path, original, 0600)
	os.Chmod(path, 0664)
	if err := ApplyInstructions(home, state, false); err != nil {
		t.Fatal(err)
	}
	first, _ := os.ReadFile(path)
	mode, _ := os.Stat(path)
	if mode.Mode().Perm() != 0664 {
		t.Fatal("user document mode changed")
	}
	if !bytes.HasPrefix(first, original) || !bytes.Contains(first, []byte("do not wait for the user")) {
		t.Fatal("missing automatic workflow or user text changed")
	}
	if err := ApplyInstructions(home, state, false); err != nil {
		t.Fatal(err)
	}
	second, _ := os.ReadFile(path)
	if !bytes.Equal(first, second) {
		t.Fatal("not idempotent")
	}
	if err := ApplyInstructions(home, state, true); err != nil {
		t.Fatal(err)
	}
	back, _ := os.ReadFile(path)
	if !bytes.Equal(back, original) {
		t.Fatal("removal lost user instructions")
	}
	ApplyInstructions(home, state, false)
	edited := bytes.Replace(first, []byte("proactively"), []byte("edited-by-user"), 1)
	os.WriteFile(path, edited, 0600)
	if err := CheckInstructions(home, state, true); err == nil {
		t.Fatal("modified block accepted")
	}
	after, _ := os.ReadFile(path)
	if !bytes.Equal(after, edited) {
		t.Fatal("conflict changed instructions")
	}
}
