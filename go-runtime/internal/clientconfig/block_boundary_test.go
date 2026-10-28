package clientconfig

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestMigrationPreservesOfficialTablesInsertedBeforeEndMarker(t *testing.T) {
	home, old, next, b, user := migrationFixture(t)
	path := filepath.Join(home, "config.toml")
	raw, _ := os.ReadFile(path)
	settings := []byte("\n[hooks.state]\n[hooks.state.\"public-hook\"]\ntrusted_hash = 'sha256:PUBLIC_DEFINITION'\n")
	raw = bytes.Replace(raw, []byte(end), append(append([]byte{}, settings...), []byte(end)...), 1)
	os.WriteFile(path, raw, 0600)
	v, e := Migrate(home, old, next, "/old/session", b, false, false)
	if e != nil || v.Boundary == "" {
		t.Fatal(v, e)
	}
	unchanged, _ := os.ReadFile(path)
	if !bytes.Equal(raw, unchanged) {
		t.Fatal("preview changed live config")
	}
	v, e = Migrate(home, old, next, "/old/session", b, true, false)
	if e != nil {
		t.Fatal(e)
	}
	journal, _ := os.ReadFile(v.Journal)
	if bytes.Contains(journal, []byte("trusted_hash")) || bytes.Contains(journal, []byte("PUBLIC_DEFINITION")) {
		t.Fatal("official trust copied into receipt")
	}
	after, _ := os.ReadFile(path)
	if !bytes.Contains(after, settings) {
		t.Fatal("official trust state changed")
	}
	if _, e = Migrate(home, old, next, "/old/session", b, true, true); e != nil {
		t.Fatal(e)
	}
	after, _ = os.ReadFile(path)
	if !bytes.Contains(after, settings) {
		t.Fatal("undo lost unrelated settings")
	}
	// The regular editor must handle the same client behavior as migration.
	after = bytes.Replace(after, []byte(end), append(append([]byte{}, settings...), []byte(end)...), 1)
	// Use a distinct new table, because duplicate TOML tables are invalid.
	after = bytes.Replace(after, settings, []byte("\n[another_client_setting]\nvalue='preserved'\n"), 1)
	os.WriteFile(path, after, 0600)
	if _, e = Apply(home, old, b, true); e != nil {
		t.Fatal("ordinary owned editor cannot reconcile boundary", e)
	}
	left, _ := os.ReadFile(path)
	if !bytes.HasPrefix(left, user) || !bytes.Contains(left, settings) || !bytes.Contains(left, []byte("another_client_setting")) {
		t.Fatal("user configuration lost")
	}
}
