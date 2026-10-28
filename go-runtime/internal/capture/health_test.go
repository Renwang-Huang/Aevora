package capture

import (
	"bytes"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"testing"
)

func TestCallbackAndCursorStateRemainBoundedAndDoNotCreateEvents(t *testing.T) {
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	initial, err := ReadCallback(root)
	if err != nil || initial["status"] != "NO_CALLBACK_OBSERVED" {
		t.Fatal(initial, err)
	}
	if err = RecordCallback(root, "NO_SIGNAL"); err != nil {
		t.Fatal(err)
	}
	callback, err := ReadCallback(root)
	if err != nil || callback["reason"] != "NO_SIGNAL" || callback["source"] != "UNVERIFIED_HANDLER_INPUT" {
		t.Fatal(callback, err)
	}
	if err = RecordCallback(root, "PRIVATE_UNKNOWN_PAYLOAD"); err == nil {
		t.Fatal("arbitrary status persisted")
	}
	scan, err := Scan(root, 1)
	if err != nil || scan.Pending != 0 {
		t.Fatal("health created learning event", scan, err)
	}
	id := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	if err = WriteCursor(root, id); err != nil {
		t.Fatal(err)
	}
	if got, e := ReadCursor(root); e != nil || got != id {
		t.Fatal("restart cursor missing", got, e)
	}
	bad := []byte("invalid cursor record")
	if err = os.WriteFile(filepath.Join(root, "capture-cursor.json"), bad, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = ReadCursor(root); err == nil {
		t.Fatal("bad cursor accepted")
	}
	if err = WriteCursor(root, id); err == nil {
		t.Fatal("live Host overwrote a corrupted cursor")
	}
	retained, e := os.ReadFile(filepath.Join(root, "capture-cursor.json"))
	if e != nil || !bytes.Equal(retained, bad) {
		t.Fatal("corrupt cursor was not retained", e)
	}
	if err = ResetCursor(root); err != nil {
		t.Fatal(err)
	}
	backups, err := filepath.Glob(filepath.Join(root, "capture-cursor-previous-*"))
	if err != nil || len(backups) != 1 {
		t.Fatal(backups, err)
	}
	raw, err := os.ReadFile(backups[0])
	if err != nil || !bytes.Equal(raw, bad) {
		t.Fatal("bad cursor evidence lost", err)
	}
	if got, e := ReadCursor(root); e != nil || got != "" {
		t.Fatal(got, e)
	}
}

func TestQuarantineAndRestorePreserveMalformedAndConflictingRecords(t *testing.T) {
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	event, err := captureformat.New("fixture", "session-1", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = Enqueue(root, event); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "capture-outbox", event.ID+".json")
	bad := []byte("malformed retained fixture")
	if err = os.WriteFile(path, bad, 0600); err != nil {
		t.Fatal(err)
	}
	if err = MoveRecord(root, event.ID, false); err != nil {
		t.Fatal(err)
	}
	if scan, e := Scan(root, 10); e != nil || scan.Pending != 0 {
		t.Fatal(scan, e)
	}
	if count, e := QuarantineCount(root); e != nil || count != 1 {
		t.Fatal(count, e)
	}
	if err = MoveRecord(root, event.ID, true); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(path)
	if err != nil || !bytes.Equal(raw, bad) {
		t.Fatal("recovery rewrote source", err)
	}
	if err = MoveRecord(root, event.ID, false); err != nil {
		t.Fatal(err)
	}
	if _, err = Enqueue(root, event); err != nil {
		t.Fatal(err)
	}
	if err = MoveRecord(root, event.ID, true); err != ErrRecoveryConflict {
		t.Fatal("restore overwrote another record", err)
	}
	kept, err := os.ReadFile(filepath.Join(root, "capture-quarantine", event.ID+".json"))
	if err != nil || !bytes.Equal(kept, bad) {
		t.Fatal("quarantine history lost", err)
	}
}
