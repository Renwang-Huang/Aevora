package capture

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
	"time"
)

var callbackReasons = map[string]bool{"INVALID_INPUT": true, "UNSUPPORTED_EVENT": true, "UNSUPPORTED_TOOL": true, "MEMORY_ECHO": true, "NO_SIGNAL": true, "UNREGISTERED_WORKSPACE": true, "WORKSPACE_UNAVAILABLE": true, "QUEUED": true, "ALREADY_QUEUED": true, "QUEUE_FULL": true, "QUEUE_UNAVAILABLE": true}

// This bounded sample records handler invocation, not authenticated Codex
// execution. Concurrent callbacks replace it; it is not a complete counter.
func RecordCallback(root, reason string) error {
	if !callbackReasons[reason] {
		return ErrInvalid
	}
	if err := platform.PrivateDir(root, false); err != nil {
		return err
	}
	raw, _ := codec.Canonical(map[string]any{"schema_version": "aevora.capture-callback/1", "reason": reason, "recorded_at": time.Now().UTC().Format(time.RFC3339Nano), "source": "UNVERIFIED_HANDLER_INPUT", "ordering": "LAST_REPLACEMENT_NOT_EVENT_ORDER"})
	return platform.Atomic(filepath.Join(root, "capture-callback.json"), raw)
}
func ReadCallback(root string) (map[string]any, error) {
	raw, err := platform.ReadPrivate(filepath.Join(root, "capture-callback.json"), 4096)
	if os.IsNotExist(err) {
		return map[string]any{"status": "NO_CALLBACK_OBSERVED", "source": "NOT_VERIFIED"}, nil
	}
	if err != nil {
		return nil, err
	}
	v, err := wire.Decode(raw, 4096)
	if err != nil {
		return nil, ErrInvalid
	}
	reason, _ := v["reason"].(string)
	stamp, _ := v["recorded_at"].(string)
	if len(v) != 5 || v["schema_version"] != "aevora.capture-callback/1" || !callbackReasons[reason] || v["source"] != "UNVERIFIED_HANDLER_INPUT" || v["ordering"] != "LAST_REPLACEMENT_NOT_EVENT_ORDER" {
		return nil, ErrInvalid
	}
	if _, err = time.Parse(time.RFC3339Nano, stamp); err != nil {
		return nil, ErrInvalid
	}
	v["status"] = "HANDLER_INVOCATION_RECORDED"
	return v, nil
}

func ReadCursor(root string) (string, error) {
	raw, err := platform.ReadPrivate(filepath.Join(root, "capture-cursor.json"), 4096)
	if os.IsNotExist(err) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	v, err := wire.Decode(raw, 4096)
	if err != nil {
		return "", ErrInvalid
	}
	last, ok := v["last"].(string)
	if len(v) != 2 || v["schema_version"] != "aevora.capture-cursor/1" || !ok || (last != "" && !captureformat.IsDigest(last)) {
		return "", ErrInvalid
	}
	return last, nil
}
func WriteCursor(root, last string) error {
	if last != "" && !captureformat.IsDigest(last) {
		return ErrInvalid
	}
	if err := platform.PrivateDir(root, false); err != nil {
		return err
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
	// A cursor that became corrupt while the Host was running must be
	// retained just like one found corrupt at startup. Reset is explicit.
	if _, err = ReadCursor(root); err != nil {
		return err
	}
	return writeCursor(root, last)
}
func writeCursor(root, last string) error {
	raw, _ := codec.Canonical(map[string]any{"schema_version": "aevora.capture-cursor/1", "last": last})
	return platform.Atomic(filepath.Join(root, "capture-cursor.json"), raw)
}
