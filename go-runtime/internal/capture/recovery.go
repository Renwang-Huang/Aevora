package capture

import (
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
)

var ErrRecoveryConflict = errors.New("AEVORA_CAPTURE_RECOVERY_CONFLICT")

// MoveRecord is an owner-requested reversible move. No source contents are
// printed, rewritten or deleted; producers and acknowledgement share its lock.
func MoveRecord(root, id string, restore bool) error {
	if !captureformat.IsDigest(id) {
		return ErrInvalid
	}
	queue, err := directory(root, true)
	if err != nil {
		return err
	}
	l, err := lock(queue)
	if err != nil {
		return err
	}
	defer l.Close()
	quarantine := filepath.Join(root, "capture-quarantine")
	if err = platform.PrivateDir(quarantine, true); err != nil {
		return err
	}
	source, dest := queue, quarantine
	if restore {
		source, dest = dest, source
	}
	entries, err := pendingEntries(dest)
	if err != nil {
		return err
	}
	if len(entries) >= MaxPending {
		return ErrFull
	}
	from, to := filepath.Join(source, id+".json"), filepath.Join(dest, id+".json")
	f, err := platform.OpenPrivate(from, os.O_RDONLY)
	if err != nil {
		return err
	}
	defer f.Close()
	before, err := f.Stat()
	if err != nil {
		return err
	}
	if _, err = os.Lstat(to); err == nil {
		return ErrRecoveryConflict
	} else if !os.IsNotExist(err) {
		return err
	}
	current, err := os.Lstat(from)
	if err != nil || !os.SameFile(before, current) {
		return ErrRecoveryConflict
	}
	if err = os.Rename(from, to); err != nil {
		return err
	}
	if err = syncDir(dest); err != nil {
		return err
	}
	return syncDir(source)
}
func QuarantineCount(root string) (int, error) {
	if err := platform.PrivateDir(root, false); err != nil {
		return 0, err
	}
	dir := filepath.Join(root, "capture-quarantine")
	if err := platform.PrivateDir(dir, false); os.IsNotExist(err) {
		return 0, nil
	} else if err != nil {
		return 0, err
	}
	entries, err := pendingEntries(dir)
	return len(entries), err
}
func ResetCursor(root string) error {
	queue, err := directory(root, true)
	if err != nil {
		return err
	}
	l, err := lock(queue)
	if err != nil {
		return err
	}
	defer l.Close()
	path := filepath.Join(root, "capture-cursor.json")
	f, err := platform.OpenPrivate(path, os.O_RDONLY)
	if err == nil {
		f.Close()
		backup, e := os.CreateTemp(root, "capture-cursor-previous-")
		if e != nil {
			return e
		}
		name := backup.Name()
		backup.Close()
		if e = os.Rename(path, name); e != nil {
			os.Remove(name)
			return e
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	return writeCursor(root, "")
}
