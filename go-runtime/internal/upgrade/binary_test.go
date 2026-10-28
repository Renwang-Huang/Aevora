package upgrade

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPinnedReplacementRefusesCorruptionAndConcurrentEdits(t *testing.T) {
	dir := t.TempDir()
	source, target := filepath.Join(dir, "new"), filepath.Join(dir, "aevora")
	os.WriteFile(source, []byte("verified-new"), 0700)
	os.WriteFile(target, []byte("old"), 0755)
	pin, _ := Digest(source)
	old, _ := Digest(target)
	if _, err := CopyPinned(source, dir, strings.Repeat("0", 64)); err == nil {
		t.Fatal("bad checksum accepted")
	}
	staged, err := CopyPinned(source, dir, pin)
	if err != nil {
		t.Fatal(err)
	}
	os.WriteFile(target, []byte("user-edit"), 0755)
	if err = Replace(staged, target, old); err != ErrChanged {
		t.Fatal("concurrent edit overwritten", err)
	}
	current, _ := Digest(target)
	if err = Replace(staged, target, current); err != nil {
		t.Fatal(err)
	}
	got, _ := Digest(target)
	if got != pin {
		t.Fatal("wrong installed bytes")
	}
	info, _ := os.Stat(target)
	if info.Mode().Perm() != 0755 {
		t.Fatal("executable mode lost")
	}
	link := filepath.Join(dir, "symlink")
	os.Symlink(source, link)
	if _, err = CopyPinned(link, dir, pin); err == nil {
		t.Fatal("symlink source accepted")
	}
}
