package clientconfig

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
)

func migrationFixture(t *testing.T) (string, string, string, Binding, []byte) {
	t.Helper()
	root := t.TempDir()
	home, old, next := filepath.Join(root, "home"), filepath.Join(root, "old"), filepath.Join(root, "next")
	platform.PrivateDir(home, true)
	platform.PrivateDir(old, true)
	user := []byte("# user bytes\nmodel='preserved'\n[mcp_servers.other]\ncommand='untouched'\n")
	os.WriteFile(filepath.Join(home, "config.toml"), user, 0600)
	if _, e := Apply(home, old, Automatic("/installed/aevora", "/old/session"), false); e != nil {
		t.Fatal(e)
	}
	os.WriteFile(filepath.Join(home, "AGENTS.md"), []byte("User instructions stay byte identical.\n"), 0644)
	if e := ApplyInstructions(home, old, false); e != nil {
		t.Fatal(e)
	}
	return home, old, next, AutomaticWorkspace("/installed/aevora", "/new/session"), user
}

func TestMigrationIncludesOwnedCaptureAndResumesSplitCommit(t *testing.T) {
	home, old, next, b, _ := migrationFixture(t)
	a, e := CaptureHook("/installed/aevora", "/old/session")
	if e != nil {
		t.Fatal(e)
	}
	if _, e = InstallCaptureHook(home, old, a); e != nil {
		t.Fatal(e)
	}
	v, e := Migrate(home, old, next, "/old/session", b, true, false)
	if e != nil || !strings.Contains(v.Capture, "NOT_GRANTED") {
		t.Fatal(v, e)
	}
	want, _ := CaptureHook(b.Command, "/new/session")
	actual, _ := os.ReadFile(filepath.Join(home, "hooks.json"))
	if !bytes.Equal(actual, want) {
		t.Fatal("callback still points at old root")
	}
	if _, e = InstallCaptureHook(home, next, want); e != nil {
		t.Fatal("new capture owner not installed", e)
	}
	if _, e = RemoveCaptureHook(home, old, a); e == nil {
		t.Fatal("old owner removed migrated callback")
	}
	raw, _ := os.ReadFile(v.Journal)
	j := migrationJournal{}
	json.Unmarshal(raw, &j)
	j.Phase = "PREPARED"
	j.Events = j.Events[:1]
	raw, _ = json.Marshal(j)
	os.WriteFile(v.Journal, raw, 0600)
	os.WriteFile(receiptPath(old, home), []byte(j.OldRaw), 0600)
	os.WriteFile(receiptPath(old, home)+".instructions", []byte(j.Instructions), 0600)
	os.WriteFile(captureReceipt(old, home), hookReceipt(a, home), 0600)
	current, _ := os.ReadFile(filepath.Join(home, "config.toml"))
	current = bytes.Replace(current, []byte(j.Next.Block), []byte(j.Old.Block), 1)
	os.WriteFile(filepath.Join(home, "config.toml"), current, 0600)
	if _, e = Migrate(home, old, next, "/old/session", b, true, false); e != nil {
		t.Fatal("split hook/config commit could not resume", e)
	}
	if _, e = Migrate(home, old, next, "/old/session", b, true, true); e != nil {
		t.Fatal(e)
	}
	actual, _ = os.ReadFile(filepath.Join(home, "hooks.json"))
	if !bytes.Equal(actual, a) {
		t.Fatal("undo did not restore callback")
	}
}

func TestMigrationRefusesModifiedCaptureBeforeChangingMCP(t *testing.T) {
	home, old, next, b, _ := migrationFixture(t)
	a, _ := CaptureHook("/installed/aevora", "/old/session")
	if _, e := InstallCaptureHook(home, old, a); e != nil {
		t.Fatal(e)
	}
	before, _ := os.ReadFile(filepath.Join(home, "config.toml"))
	edited := append(a, []byte(" ")...)
	os.WriteFile(filepath.Join(home, "hooks.json"), edited, 0600)
	if _, e := Migrate(home, old, next, "/old/session", b, true, false); e == nil {
		t.Fatal("modified callback adopted")
	}
	after, _ := os.ReadFile(filepath.Join(home, "config.toml"))
	if !bytes.Equal(before, after) {
		t.Fatal("refusal changed MCP")
	}
}

func TestMigrationPreviewResumeUndoPreservesUserBytes(t *testing.T) {
	home, old, next, b, user := migrationFixture(t)
	config := filepath.Join(home, "config.toml")
	before, _ := os.ReadFile(config)
	agents, _ := os.ReadFile(filepath.Join(home, "AGENTS.md"))
	if v, e := Migrate(home, old, next, "/old/session", b, false, false); e != nil || v.Status != "PREVIEW" {
		t.Fatal(v, e)
	}
	if _, e := os.Lstat(next); !os.IsNotExist(e) {
		t.Fatal("preview wrote state", e)
	}
	v, e := Migrate(home, old, next, "/old/session", b, true, false)
	if e != nil || v.Status != "COMPLETED" {
		t.Fatal(v, e)
	}
	after, _ := os.ReadFile(config)
	a, _ := os.ReadFile(filepath.Join(home, "AGENTS.md"))
	if !bytes.HasPrefix(after, user) || !bytes.Equal(a, agents) {
		t.Fatal("personal bytes changed")
	}
	if _, e := Apply(home, old, b, true); e == nil {
		t.Fatal("old owner removed destination binding")
	}
	journal, _ := os.ReadFile(v.Journal)
	if _, e = Migrate(home, old, next, "/old/session", b, true, false); e != nil {
		t.Fatal("retry failed", e)
	}
	again, _ := os.ReadFile(v.Journal)
	if !bytes.Equal(journal, again) {
		t.Fatal("completed retry grew journal")
	}
	if _, e = Migrate(home, old, next, "/old/session", b, true, true); e != nil {
		t.Fatal("undo failed", e)
	}
	restored, _ := os.ReadFile(config)
	if !bytes.Equal(restored, before) {
		t.Fatal("undo did not restore only the old block")
	}
	if _, e = Migrate(home, old, next, "/old/session", b, true, true); e != nil {
		t.Fatal("undo retry", e)
	}
	if _, e = Migrate(home, old, next, "/old/session", b, true, false); e != nil {
		t.Fatal("forward after undo", e)
	}
	if _, e = Apply(home, next, b, true); e != nil {
		t.Fatal("new owner cannot remove binding", e)
	}
	left, _ := os.ReadFile(config)
	if !bytes.Equal(left, user) {
		t.Fatal("remove changed user configuration")
	}
}

func TestMigrationReconcilesBothSidesOfConfigCommit(t *testing.T) {
	for _, committed := range []bool{false, true} {
		t.Run(map[bool]string{false: "before", true: "after"}[committed], func(t *testing.T) {
			home, old, next, b, _ := migrationFixture(t)
			v, e := Migrate(home, old, next, "/old/session", b, true, false)
			if e != nil {
				t.Fatal(e)
			}
			raw, _ := os.ReadFile(v.Journal)
			j := migrationJournal{}
			json.Unmarshal(raw, &j)
			// Reconstruct durable PREPARED state, rather than deleting the original
			// evidence in an installed project. New final receipts already exist.
			j.Phase = "PREPARED"
			j.Events = j.Events[:1]
			raw, _ = json.Marshal(j)
			os.WriteFile(v.Journal, raw, 0600)
			os.WriteFile(receiptPath(old, home), []byte(j.OldRaw), 0600)
			os.WriteFile(receiptPath(old, home)+".instructions", []byte(j.Instructions), 0600)
			if !committed {
				current, _ := os.ReadFile(filepath.Join(home, "config.toml"))
				current = bytes.Replace(current, []byte(j.Next.Block), []byte(j.Old.Block), 1)
				os.WriteFile(filepath.Join(home, "config.toml"), current, 0600)
			}
			if _, e = Migrate(home, old, next, "/old/session", b, true, false); e != nil {
				t.Fatal("reconciliation failed", e)
			}
			current, _ := os.ReadFile(filepath.Join(home, "config.toml"))
			if !ownedBlock(current, j.Next) {
				t.Fatal("wrong active owner")
			}
		})
	}
}

func TestMigrationRejectsEditedOrForeignBindingAndPreservesChanges(t *testing.T) {
	home, old, next, b, _ := migrationFixture(t)
	if _, e := Migrate(home, old, next, "/foreign/root", b, true, false); e == nil {
		t.Fatal("wrong source scope accepted")
	}
	if _, e := Migrate(home, old, next, "/old/session", b, true, false); e != nil {
		t.Fatal(e)
	}
	path := filepath.Join(home, "config.toml")
	raw, _ := os.ReadFile(path)
	raw = append(raw, []byte("[mcp_servers.aevora.env]\nCUSTOM='user-owned'\n")...)
	os.WriteFile(path, raw, 0600)
	if _, e := Migrate(home, old, next, "/old/session", b, true, true); e == nil {
		t.Fatal("user edited block overwritten")
	}
	after, _ := os.ReadFile(path)
	if !bytes.Equal(raw, after) {
		t.Fatal("refusal changed config")
	}
}
