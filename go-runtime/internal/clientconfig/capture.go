package clientconfig

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
)

var ErrCaptureHookConflict = errors.New("AEVORA_CAPTURE_HOOK_CONFLICT")

func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'" }

// CaptureHook constructs a single-purpose user hook. It never edits any other
// hook source or grants Codex's independent hook trust.
func CaptureHook(binary, root string) ([]byte, error) {
	if runtime.GOOS != "linux" || !filepath.IsAbs(binary) || !filepath.IsAbs(root) || strings.ContainsAny(binary+root, "\x00\r\n") {
		return nil, platform.ErrUnsafe
	}
	command := shellQuote(binary) + " capture hook --session-root " + shellQuote(root)
	definition := map[string]any{
		"description": "Aevora managed bounded diagnostic capture; source claims remain untrusted",
		"hooks": map[string]any{"PostToolUse": []any{map[string]any{
			"matcher": "^(Bash|apply_patch)$", "hooks": []any{map[string]any{
				"type": "command", "command": command, "timeout": 3,
			}},
		}}},
	}
	raw, err := json.MarshalIndent(definition, "", "  ")
	return append(raw, '\n'), err
}

func captureReceipt(state, home string) string {
	hash := sha256.Sum256([]byte(home))
	return filepath.Join(state, "capture-hook-"+hex.EncodeToString(hash[:])+".json")
}

func hookReceipt(raw []byte, home string) []byte {
	hash := sha256.Sum256(raw)
	b, _ := json.Marshal(map[string]string{"schema_version": "aevora.capture-hook-receipt/1", "home": home, "sha256": hex.EncodeToString(hash[:])})
	return b
}

// createExclusive links a fully synced private temp file into place. A racing
// user file wins; it is never overwritten. Directory sync makes creation and
// cleanup durable. An interrupted install remains an unowned file, not a
// reason to delete or adopt it silently.
func createExclusive(home, target string, raw []byte) error {
	tmp, err := os.CreateTemp(home, ".aevora-capture-")
	if err != nil {
		return err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err = tmp.Write(raw); err == nil {
		err = tmp.Sync()
	}
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	if err = os.Link(name, target); err != nil {
		if os.IsExist(err) {
			return ErrCaptureHookConflict
		}
		return err
	}
	if err = os.Remove(name); err != nil {
		return err
	}
	d, err := os.Open(home)
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}

// InstallCaptureHook refuses existing or changed user files. It writes an
// ownership receipt only after exclusive creation has succeeded.
func InstallCaptureHook(home, state string, raw []byte) (string, error) {
	if err := platform.PrivateDir(home, false); err != nil {
		return "", err
	}
	if err := platform.PrivateDir(state, true); err != nil {
		return "", err
	}
	lock, e := platform.Lock(filepath.Join(state, "capture.lock"))
	if e != nil {
		return "", e
	}
	defer lock.Close()
	target, receipt := filepath.Join(home, "hooks.json"), captureReceipt(state, home)
	want := hookReceipt(raw, home)
	if prior, err := platform.ReadPrivate(target, 4096); err == nil {
		owner, e := platform.ReadPrivate(receipt, 4096)
		if e == nil && bytes.Equal(prior, raw) && bytes.Equal(owner, want) {
			return "UNCHANGED", nil
		}
		return "", ErrCaptureHookConflict
	} else if !os.IsNotExist(err) {
		return "", err
	}
	if _, err := os.Lstat(receipt); err == nil || !os.IsNotExist(err) {
		return "", ErrCaptureHookConflict
	}
	if err := createExclusive(home, target, raw); err != nil {
		return "", err
	}
	if err := platform.Exclusive(receipt, want); err != nil {
		// Preserve the installed file and report the partial setup. It must not
		// be silently deleted, overwritten or treated as owned on a retry.
		return "", errors.New("AEVORA_CAPTURE_HOOK_RECEIPT_FAILED")
	}
	return "INSTALLED", nil
}

// Remove only an unchanged definition with the corresponding receipt. A user
// edit or missing receipt is a conflict, not permission to remove the file.
func RemoveCaptureHook(home, state string, raw []byte) (string, error) {
	if err := platform.PrivateDir(home, false); err != nil {
		return "", err
	}
	if err := platform.PrivateDir(state, false); err != nil {
		return "", err
	}
	lock, e := platform.Lock(filepath.Join(state, "capture.lock"))
	if e != nil {
		return "", e
	}
	defer lock.Close()
	target, receipt := filepath.Join(home, "hooks.json"), captureReceipt(state, home)
	prior, err := platform.ReadPrivate(target, 4096)
	if err != nil {
		return "", err
	}
	owner, err := platform.ReadPrivate(receipt, 4096)
	if err != nil || !bytes.Equal(prior, raw) || !bytes.Equal(owner, hookReceipt(raw, home)) {
		return "", ErrCaptureHookConflict
	}
	if err = os.Remove(target); err != nil {
		return "", err
	}
	d, err := os.Open(home)
	if err != nil {
		return "", err
	}
	err = d.Sync()
	d.Close()
	if err != nil {
		return "", err
	}
	if err = os.Remove(receipt); err != nil {
		return "", err
	}
	return "REMOVED", nil
}

// InspectCaptureHook reads only the managed definition and its local receipt;
// Codex's independent trust state is not inferred from file presence.
func InspectCaptureHook(home, state string) string {
	raw, err := platform.ReadPrivate(filepath.Join(home, "hooks.json"), 4096)
	if os.IsNotExist(err) {
		return "NOT_INSTALLED"
	}
	if err != nil {
		return "UNREADABLE"
	}
	owner, err := platform.ReadPrivate(captureReceipt(state, home), 4096)
	if err != nil || !bytes.Equal(owner, hookReceipt(raw, home)) {
		return "MODIFIED_OR_UNMANAGED"
	}
	return "OWNED_DEFINITION"
}
