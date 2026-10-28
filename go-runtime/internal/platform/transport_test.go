//go:build linux || darwin

package platform

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLongMetadataPathUsesPrivateShortSocketAndPreservesEvidence(t *testing.T) {
	folder := filepath.Join(t.TempDir(), strings.Repeat("metadata-", 18))
	if e := PrivateDir(folder, true); e != nil {
		t.Fatal(e)
	}
	marker := filepath.Join(folder, "evidence.json")
	if e := Exclusive(marker, []byte("retained")); e != nil {
		t.Fatal(e)
	}
	address := Address(folder)
	if len(address) > 103 || address == filepath.Join(folder, "mcp.sock") {
		t.Fatal("long Unix address not isolated")
	}
	listener, e := Listen(address)
	if e != nil {
		t.Fatal(e)
	}
	if e = PrivateDir(filepath.Dir(address), false); e != nil {
		listener.Close()
		t.Fatal(e)
	}
	if e = listener.Close(); e != nil {
		t.Fatal(e)
	}
	if _, e = os.Lstat(address); !os.IsNotExist(e) {
		t.Fatal("owned socket remained", e)
	}
	if _, e = os.Lstat(filepath.Dir(address)); !os.IsNotExist(e) {
		t.Fatal("owned short socket directory remained", e)
	}
	raw, e := os.ReadFile(marker)
	if e != nil || string(raw) != "retained" {
		t.Fatal("persistent evidence was changed", e)
	}
}
