package clientconfig

import (
	"bytes"
	"os"
	"path/filepath"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
)

type captureMigration struct{ Old, Next string }

func planCaptureMigration(home, source, target string, old, next Binding) (*captureMigration, error) {
	receipt, e := platform.ReadPrivate(captureReceipt(source, home), 4096)
	if os.IsNotExist(e) {
		return nil, nil
	}
	if e != nil {
		return nil, e
	}
	a, e := CaptureHook(old.Command, managedRoot(old))
	if e != nil {
		return nil, e
	}
	b, e := CaptureHook(next.Command, managedRoot(next))
	if e != nil {
		return nil, e
	}
	current, e := platform.ReadPrivate(filepath.Join(home, "hooks.json"), 4096)
	if e != nil || !bytes.Equal(current, a) || !bytes.Equal(receipt, hookReceipt(a, home)) {
		return nil, ErrCaptureHookConflict
	}
	if _, e = os.Lstat(captureReceipt(target, home)); !os.IsNotExist(e) {
		return nil, ErrCaptureHookConflict
	}
	return &captureMigration{string(a), string(b)}, nil
}
func checkCaptureMigration(home, source, target string, c *captureMigration, old, next Binding) error {
	if c == nil {
		return nil
	}
	a, e := CaptureHook(old.Command, managedRoot(old))
	if e != nil {
		return e
	}
	b, e := CaptureHook(next.Command, managedRoot(next))
	if e != nil {
		return e
	}
	if string(a) != c.Old || string(b) != c.Next {
		return ErrCaptureHookConflict
	}
	current, e := platform.ReadPrivate(filepath.Join(home, "hooks.json"), 4096)
	if e != nil || (!bytes.Equal(current, a) && !bytes.Equal(current, b)) {
		return ErrCaptureHookConflict
	}
	for path, want := range map[string][]byte{captureReceipt(source, home): hookReceipt(a, home), captureReceipt(target, home): hookReceipt(b, home)} {
		current, e := platform.ReadPrivate(path, 4096)
		if e == nil && !bytes.Equal(current, want) {
			return ErrCaptureHookConflict
		}
		if e != nil && !os.IsNotExist(e) {
			return e
		}
	}
	return nil
}
func commitCaptureMigration(home, owner string, c *captureMigration, undo bool) error {
	if c == nil {
		return nil
	}
	from, to := c.Old, c.Next
	if undo {
		from, to = to, from
	}
	if e := writeSame(captureReceipt(owner, home), hookReceipt([]byte(to), home), 4096); e != nil {
		return e
	}
	path := filepath.Join(home, "hooks.json")
	current, e := platform.ReadPrivate(path, 4096)
	if e != nil {
		return e
	}
	if string(current) == to {
		return nil
	}
	if string(current) != from {
		return ErrCaptureHookConflict
	}
	return platform.AtomicLimit(path, []byte(to), 4096)
}
func archiveCaptureMigration(home, other string, c *captureMigration, undo bool) error {
	if c == nil {
		return nil
	}
	from := c.Old
	if undo {
		from = c.Next
	}
	return archiveSame(captureReceipt(other, home), hookReceipt([]byte(from), home), 4096)
}
