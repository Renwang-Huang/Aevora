package clientconfig

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
)

func TestCaptureHookInstallAndRemovalPreserveUserChanges(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("Codex shell hook setup is currently supported on Linux")
	}
	base := t.TempDir()
	home, state := filepath.Join(base, "codex"), filepath.Join(base, "state")
	if err := os.Mkdir(home, 0700); err != nil {
		t.Fatal(err)
	}
	raw, err := CaptureHook("/path/with'quote/aevora", "/private/root")
	if err != nil {
		t.Fatal(err)
	}
	var definition map[string]any
	if json.Unmarshal(raw, &definition) != nil || !strings.Contains(string(raw), `with'\\''quote`) {
		t.Fatal("invalid or unsafe shell quoting", string(raw))
	}
	path := filepath.Join(home, "hooks.json")
	if got := InspectCaptureHook(home, state); got != "NOT_INSTALLED" {
		t.Fatal(got)
	}
	foreign := []byte("{\"hooks\":{}}\n")
	if err = os.WriteFile(path, foreign, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = InstallCaptureHook(home, state, raw); !errors.Is(err, ErrCaptureHookConflict) {
		t.Fatal("existing user hook accepted", err)
	}
	got, _ := os.ReadFile(path)
	if !bytes.Equal(got, foreign) {
		t.Fatal("existing user hook changed")
	}
	if err = os.Remove(path); err != nil {
		t.Fatal(err)
	}
	if result, err := InstallCaptureHook(home, state, raw); err != nil || result != "INSTALLED" {
		t.Fatal(result, err)
	}
	if result, err := InstallCaptureHook(home, state, raw); err != nil || result != "UNCHANGED" {
		t.Fatal(result, err)
	}
	if got := InspectCaptureHook(home, state); got != "OWNED_DEFINITION" {
		t.Fatal(got)
	}
	if err = os.WriteFile(path, foreign, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = RemoveCaptureHook(home, state, raw); !errors.Is(err, ErrCaptureHookConflict) {
		t.Fatal("changed hook was removed", err)
	}
	if got := InspectCaptureHook(home, state); got != "MODIFIED_OR_UNMANAGED" {
		t.Fatal(got)
	}
	if err = os.WriteFile(path, raw, 0600); err != nil {
		t.Fatal(err)
	}
	if result, err := RemoveCaptureHook(home, state, raw); err != nil || result != "REMOVED" {
		t.Fatal(result, err)
	}
	if _, err = os.Lstat(path); !os.IsNotExist(err) {
		t.Fatal("owned hook remains", err)
	}
}

func TestCaptureHookExclusiveCreationAndUnownedRecovery(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("Codex shell hook setup is currently supported on Linux")
	}
	base := t.TempDir()
	home, state := filepath.Join(base, "codex"), filepath.Join(base, "state")
	if err := os.Mkdir(home, 0700); err != nil {
		t.Fatal(err)
	}
	raw, _ := CaptureHook("/opt/aevora", "/private/root")
	path := filepath.Join(home, "hooks.json")
	var group sync.WaitGroup
	results := make(chan error, 2)
	for i := 0; i < 2; i++ {
		group.Add(1)
		go func() { defer group.Done(); results <- createExclusive(home, path, raw) }()
	}
	group.Wait()
	close(results)
	success, conflicts := 0, 0
	for err := range results {
		if err == nil {
			success++
		} else if errors.Is(err, ErrCaptureHookConflict) {
			conflicts++
		} else {
			t.Fatal(err)
		}
	}
	if success != 1 || conflicts != 1 {
		t.Fatal(success, conflicts)
	}
	// A crash between file creation and the ownership receipt cannot cause
	// a retry to adopt or remove a file of uncertain origin.
	if _, err := InstallCaptureHook(home, state, raw); !errors.Is(err, ErrCaptureHookConflict) {
		t.Fatal("unowned file silently adopted", err)
	}
	if _, err := RemoveCaptureHook(home, state, raw); !errors.Is(err, ErrCaptureHookConflict) {
		t.Fatal("unowned file silently removed", err)
	}
}
