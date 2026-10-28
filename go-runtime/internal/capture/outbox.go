// Package capture implements a bounded, private outbox for sanitized Codex
// diagnostics. Hook input, commands, output, prompts, paths and transcripts
// never enter the queue. Records remain untrusted caller-originated claims.
package capture

import (
	"bytes"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

const MaxInput = 262144
const MaxPending = 4096

// The elapsed budget is checked between files; one bounded read is always
// attempted so a slow filesystem cannot leave the cursor permanently stuck.
const ScanTimeBudget = 100 * time.Millisecond

var identity = regexp.MustCompile(`^[A-Za-z0-9_-]{1,128}$`)
var ErrInvalid = captureformat.ErrInvalid
var ErrFull = errors.New("AEVORA_CAPTURE_OUTBOX_FULL")

type Event = captureformat.Event

var signalRules = []struct{ needle, signal string }{
	{"jsondecodeerror", "JSON_DECODE_ERROR"},
	{"aevora_run_context_conflict", "RUN_CONTEXT_CONFLICT"},
	{"aevora_reconnect_required", "RECONNECT_REQUIRED"},
	{"connection refused", "CONNECTION_REFUSED"},
	{"permission denied", "PERMISSION_DENIED"},
}

func find(v any, needle string) bool {
	switch x := v.(type) {
	case string:
		return strings.Contains(strings.ToLower(x), needle)
	case []any:
		for _, y := range x {
			if find(y, needle) {
				return true
			}
		}
	case map[string]any:
		for _, y := range x {
			if find(y, needle) {
				return true
			}
		}
	}
	return false
}

// FromHook maps only documented PostToolUse fields to a closed vocabulary.
// A project name is a routing hint from an untrusted hook, not verified scope.
func FromHook(raw []byte) (Event, bool, error) {
	e, reason, err := ClassifyHook(raw)
	return e, reason == "SIGNAL", err
}

func ClassifyHook(raw []byte) (Event, string, error) {
	return classifyHook("", raw)
}

func ClassifyHookForRoot(root string, raw []byte) (Event, string, error) {
	return classifyHook(root, raw)
}

func classifyHook(root string, raw []byte) (Event, string, error) {
	value, err := wire.Decode(raw, MaxInput)
	if err != nil {
		return Event{}, "INVALID_INPUT", ErrInvalid
	}
	if value["hook_event_name"] != "PostToolUse" {
		return Event{}, "UNSUPPORTED_EVENT", nil
	}
	tool, _ := value["tool_name"].(string)
	switch tool {
	case "Bash":
		tool = "BASH"
	case "apply_patch":
		tool = "PATCH"
	default:
		return Event{}, "UNSUPPORTED_TOOL", nil
	}
	input, ok := value["tool_input"].(map[string]any)
	if !ok {
		return Event{}, "INVALID_INPUT", ErrInvalid
	}
	_, ok = input["command"].(string)
	if !ok {
		return Event{}, "INVALID_INPUT", ErrInvalid
	}
	// Match complete memory-response envelopes, never project names or paths
	// in commands. A failed Aevora command is a useful diagnostic, not recall.
	if memoryEcho(value["tool_response"]) {
		return Event{}, "MEMORY_ECHO", nil
	}
	var signal string
	for _, rule := range signalRules {
		if find(value["tool_response"], rule.needle) {
			signal = rule.signal
			break
		}
	}
	if signal == "" {
		return Event{}, "NO_SIGNAL", nil
	}
	session, _ := value["session_id"].(string)
	turn, _ := value["turn_id"].(string)
	call, _ := value["tool_use_id"].(string)
	directory, _ := value["cwd"].(string)
	if !identity.MatchString(session) || !identity.MatchString(turn) || !identity.MatchString(call) || !filepath.IsAbs(directory) {
		return Event{}, "INVALID_INPUT", ErrInvalid
	}
	var project local.Project
	if root != "" {
		project, err = local.SelectAutomaticWorkspace(root, directory)
	}
	if root == "" || os.IsNotExist(err) {
		project, err = local.SelectWorkspace(directory)
	}
	if errors.Is(err, local.ErrProjectNotRegistered) {
		return Event{}, "UNREGISTERED_WORKSPACE", nil
	}
	if err != nil {
		return Event{}, "WORKSPACE_UNAVAILABLE", err
	}
	e, err := captureformat.New(project.Name, session, turn, call, tool, signal)
	if err != nil {
		return Event{}, "INVALID_INPUT", err
	}
	return e, "SIGNAL", nil
}

func directory(root string, create bool) (string, error) {
	if err := platform.PrivateDir(root, false); err != nil {
		return "", err
	}
	dir := filepath.Join(root, "capture-outbox")
	if err := platform.PrivateDir(dir, create); err != nil {
		return "", err
	}
	return dir, nil
}

// syncDir uses the existing atomic replacement primitive to synchronize the
// directory after exclusive creation/removal. Its marker carries no payload.
func syncDir(dir string) error { return platform.Atomic(filepath.Join(dir, ".sync"), []byte("1")) }

func lock(dir string) (*os.File, error) {
	deadline := time.Now().Add(2 * time.Second)
	for {
		f, err := platform.Lock(filepath.Join(dir, ".lock"))
		if err == nil {
			return f, nil
		}
		if err.Error() != "AEVORA_BACKEND_ALREADY_OWNED" || time.Now().After(deadline) {
			return nil, err
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func Enqueue(root string, e Event) (bool, error) {
	if !captureformat.Valid(e) {
		return false, ErrInvalid
	}
	dir, err := directory(root, true)
	if err != nil {
		return false, err
	}
	l, err := lock(dir)
	if err != nil {
		return false, err
	}
	defer l.Close()
	entries, err := pendingEntries(dir)
	if err != nil {
		return false, err
	}
	raw, err := codec.Canonical(e.Map())
	if err != nil {
		return false, err
	}
	path := filepath.Join(dir, e.ID+".json")
	old, err := platform.ReadPrivate(path, 4096)
	if err == nil {
		if !bytes.Equal(old, raw) {
			return false, ErrInvalid
		}
		return false, syncDir(dir)
	}
	if !os.IsNotExist(err) {
		return false, err
	}
	if len(entries) >= MaxPending {
		return false, ErrFull
	}
	// The ID commits to all persisted fields; concurrent writers for the same
	// ID can therefore only write the same record. Atomic rename hides partials.
	if err = platform.Atomic(path, raw); err != nil {
		return false, err
	}
	return true, nil
}

func pendingEntries(dir string) ([]string, error) {
	f, err := os.Open(dir)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var names []string
	seen := 0
	for {
		entries, e := f.ReadDir(128)
		for _, entry := range entries {
			seen++
			if seen > MaxPending+128 {
				return nil, ErrFull
			}
			name := entry.Name()
			if strings.HasSuffix(name, ".json") && captureformat.IsDigest(strings.TrimSuffix(name, ".json")) {
				names = append(names, name)
			}
		}
		if e == io.EOF {
			break
		}
		if e != nil {
			return nil, e
		}
	}
	sort.Strings(names)
	return names, nil
}

type ScanResult struct {
	Events  []Event
	Pending int
	Scanned int
	Invalid int
	Last    string
	Limited bool
}

// Invalid entries are retained and counted, while other events may continue.
// Invalid is a lower bound when the requested batch limit ends the scan early.
func Scan(root string, limit int) (ScanResult, error) {
	return ScanSince(root, limit, "")
}

// ScanSince walks a bounded sorted batch and wraps after the end so an
// unauthorized or invalid event cannot starve unrelated later entries.
func ScanSince(root string, limit int, after string) (ScanResult, error) {
	started := time.Now()
	result := ScanResult{Events: []Event{}}
	if limit < 1 || limit > 128 || (after != "" && !captureformat.IsDigest(after)) {
		return result, ErrInvalid
	}
	dir, err := directory(root, false)
	if os.IsNotExist(err) {
		return result, nil
	}
	if err != nil {
		return result, err
	}
	names, err := pendingEntries(dir)
	if err != nil {
		return result, err
	}
	result.Pending = len(names)
	start := 0
	if after != "" {
		start = sort.Search(len(names), func(i int) bool { return names[i] > after+".json" })
		if start == len(names) {
			start = 0
		}
	}
	for _, name := range names[start:] {
		if result.Scanned == limit || (result.Scanned > 0 && time.Since(started) >= ScanTimeBudget) {
			break
		}
		result.Scanned++
		result.Last = strings.TrimSuffix(name, ".json")
		raw, e := platform.ReadPrivate(filepath.Join(dir, name), 4096)
		if e != nil {
			result.Invalid++
			continue
		}
		v, e := wire.Decode(raw, 4096)
		if e != nil {
			result.Invalid++
			continue
		}
		canonical, e := codec.Canonical(v)
		if e != nil || !bytes.Equal(canonical, raw) {
			result.Invalid++
			continue
		}
		event, e := captureformat.Parse(v)
		if e != nil || name != event.ID+".json" {
			result.Invalid++
			continue
		}
		result.Events = append(result.Events, event)
	}
	result.Limited = result.Scanned < len(names)
	return result, nil
}

func Pending(root string, limit int) ([]Event, error) {
	result, err := Scan(root, limit)
	if err != nil {
		return nil, err
	}
	if result.Invalid > 0 {
		return nil, ErrInvalid
	}
	return result.Events, nil
}

// Acknowledgement is valid only for the exact sanitized event persisted by
// the receiver. A changed or unsafe spool file is preserved and rejected.
func Acknowledge(root string, e Event, receipt string) error {
	if !captureformat.Valid(e) {
		return ErrInvalid
	}
	expected, err := codec.Digest(e.Map())
	if err != nil || expected != receipt {
		return ErrInvalid
	}
	dir, err := directory(root, false)
	if err != nil {
		return err
	}
	l, err := lock(dir)
	if err != nil {
		return err
	}
	defer l.Close()
	path := filepath.Join(dir, e.ID+".json")
	raw, err := platform.ReadPrivate(path, 4096)
	if err != nil {
		return err
	}
	want, err := codec.Canonical(e.Map())
	if err != nil || !bytes.Equal(raw, want) {
		return ErrInvalid
	}
	if err = os.Remove(path); err != nil {
		return err
	}
	return syncDir(dir)
}
