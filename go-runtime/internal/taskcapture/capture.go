// Package taskcapture adapts official completed items to bounded public observations.
package taskcapture

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

const MaxInput = 262144

var testName = regexp.MustCompile(`^Test[A-Za-z0-9_]{1,96}$`)

func Project(raw []byte, project, task string) (domain.Map, error) {
	v, err := wire.Decode(raw, MaxInput)
	if err != nil {
		return nil, err
	}
	if v["method"] != "item/completed" {
		return nil, nil
	}
	p := domain.M(v["params"])
	item := domain.M(p["item"])
	kind := domain.S(item["type"])
	if kind != "commandExecution" && kind != "fileChange" {
		return nil, nil
	}
	status := strings.ToUpper(domain.S(item["status"]))
	if status != "COMPLETED" && status != "FAILED" && status != "DECLINED" {
		return nil, nil
	}
	action, ekind := "COMMAND", "COMMAND"
	summary := ""
	var code any
	if kind == "fileChange" {
		action = "FILE_CHANGE"
		ekind = "CHANGE"
		summary = fmt.Sprintf("File change %s; changed files: %d", status, len(domain.A(item["changes"])))
	} else {
		action = commandAction(domain.S(item["command"]))
		code = item["exitCode"]
		if code != nil && domain.I(code) != 0 && status == "COMPLETED" {
			status = "FAILED"
		}
		names := map[string]bool{}
		output := domain.S(item["aggregatedOutput"])
		if len(output) <= MaxInput {
			for _, line := range strings.Split(output, "\n") {
				var row struct{ Action, Test string }
				if json.Unmarshal([]byte(line), &row) == nil && testName.MatchString(row.Test) && (row.Action == "pass" || row.Action == "fail") {
					names[row.Test] = true
				}
			}
		}
		tests := []string{}
		for name := range names {
			tests = append(tests, name)
		}
		sort.Strings(tests)
		if len(tests) > 8 {
			tests = tests[:8]
		}
		summary = fmt.Sprintf("%s %s", action, status)
		if len(tests) > 0 {
			summary += "; tests: " + strings.Join(tests, ", ")
		}
	}
	e := domain.Map{"schema_version": domain.TaskEventVersion, "project": project, "task_ref": task, "session_ref": p["threadId"], "turn_ref": p["turnId"], "item_ref": item["id"], "kind": ekind, "status": status, "action": action, "summary": summary, "exit_code": code, "occurred_at": nil, "revision": nil}
	if err = domain.ValidateTaskEvent(e); err != nil {
		return nil, err
	}
	return e, nil
}
func folder(root string) string { return filepath.Join(root, "task-outbox") }
func Enqueue(root string, e domain.Map) error {
	if domain.ValidateTaskEvent(e) != nil {
		return domain.ErrInvalid
	}
	dir := folder(root)
	if err := platform.PrivateDir(dir, true); err != nil {
		return err
	}
	guard, err := platform.Lock(filepath.Join(root, "task-queue.lock"))
	if err != nil {
		return err
	}
	defer guard.Close()
	entries, err := os.ReadDir(dir)
	if err != nil {
		return err
	}
	if len(entries) >= 1024 {
		return errors.New("AEVORA_TASK_OUTBOX_FULL")
	}
	raw, err := json.Marshal(e)
	if err != nil {
		return err
	}
	path := filepath.Join(dir, strings.TrimPrefix(domain.TaskSourceID(e), "external-observation:task:")+".json")
	if err = platform.Exclusive(path, raw); os.IsExist(err) {
		old, e2 := platform.ReadPrivate(path, MaxInput)
		if e2 != nil || !bytes.Equal(old, raw) {
			return domain.ErrConflict
		}
		return nil
	}
	return err
}

type Pending struct {
	Path  string
	Event domain.Map
}

func Scan(root string, limit int) ([]Pending, int, error) {
	if limit < 1 || limit > 64 {
		return nil, 0, domain.ErrInvalid
	}
	dir := folder(root)
	if err := platform.PrivateDir(dir, true); err != nil {
		return nil, 0, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, 0, err
	}
	out := []Pending{}
	invalid := 0
	// Rotate over every entry, including malformed ones. This is an outbox scan
	// cursor only; it is never an incremental memory processing watermark.
	cursorPath := filepath.Join(root, "task-cursor.json")
	last := ""
	if raw, e := platform.ReadPrivate(cursorPath, 4096); e == nil {
		v, e := wire.Decode(raw, 4096)
		if e != nil || !validCursor(v) {
			return nil, 0, domain.ErrInvalid
		}
		last = domain.S(v["last"])
	} else if !os.IsNotExist(e) {
		return nil, 0, e
	}
	start := sort.Search(len(entries), func(i int) bool { return entries[i].Name() > last })
	if start == len(entries) {
		start = 0
	}
	scanned := 0
	for i := 0; i < len(entries) && scanned < limit; i++ {
		entry := entries[(start+i)%len(entries)]
		scanned++
		last = entry.Name()
		path := filepath.Join(dir, entry.Name())
		raw, e := platform.ReadPrivate(path, MaxInput)
		var v domain.Map
		if e == nil {
			v, e = wire.Decode(raw, MaxInput)
		}
		if e != nil || domain.ValidateTaskEvent(v) != nil || entry.Name() != strings.TrimPrefix(domain.TaskSourceID(v), "external-observation:task:")+".json" {
			invalid++
			continue
		}
		out = append(out, Pending{path, v})
	}
	if scanned > 0 {
		if raw, e := platform.ReadPrivate(cursorPath, 4096); e == nil {
			v, e := wire.Decode(raw, 4096)
			if e != nil || !validCursor(v) {
				return nil, invalid, domain.ErrInvalid
			}
		} else if !os.IsNotExist(e) {
			return nil, invalid, e
		}
		raw, _ := json.Marshal(domain.Map{"schema_version": "aevora.task-scan/1", "last": last})
		if e := platform.Atomic(cursorPath, raw); e != nil {
			return nil, invalid, e
		}
	}
	return out, invalid, nil
}
func Ack(p Pending) error {
	raw, err := platform.ReadPrivate(p.Path, MaxInput)
	if err != nil {
		return err
	}
	v, err := wire.Decode(raw, MaxInput)
	if err != nil || domain.H(v) != domain.H(p.Event) {
		return domain.ErrConflict
	}
	return os.Remove(p.Path)
}
func Record(root, client, reason string) error {
	if client != "codex" && client != "codex1" && client != "codex2" {
		return domain.ErrInvalid
	}
	dir := filepath.Join(root, "task-clients")
	if err := platform.PrivateDir(dir, true); err != nil {
		return err
	}
	raw, _ := json.Marshal(domain.Map{"schema_version": "aevora.task-client/1", "client": client, "state": reason, "observed_at": time.Now().UTC().Format(time.RFC3339Nano), "authority": "LOCAL_ADAPTER_LABEL_NOT_AUTHENTICATED_HOME"})
	return platform.Atomic(filepath.Join(dir, client+".json"), raw)
}
func Status(root string) domain.Map {
	localCheck := domain.Map{"status": "NOT_OBSERVED", "authority": "UNKNOWN"}
	if raw, err := platform.ReadPrivate(filepath.Join(root, "local-check-status.json"), 4096); err == nil {
		if value, err := wire.Decode(raw, 4096); err == nil && value["schema_version"] == "aevora.local-check-capture/1" {
			localCheck = value
		} else {
			localCheck = domain.Map{"status": "UNAVAILABLE", "reason": "INVALID_LOCAL_CHECK_STATUS"}
		}
	} else if !os.IsNotExist(err) {
		localCheck = domain.Map{"status": "UNAVAILABLE", "reason": "LOCAL_CHECK_STATUS_READ_FAILED"}
	}
	clients := []any{}
	for _, name := range []string{"codex", "codex1", "codex2"} {
		value := domain.Map{"client": name, "state": "NOT_OBSERVED", "authority": "UNKNOWN"}
		if raw, e := platform.ReadPrivate(filepath.Join(root, "task-clients", name+".json"), 4096); e == nil {
			if v, e := wire.Decode(raw, 4096); e == nil {
				value = v
			}
		}
		clients = append(clients, value)
	}
	drainer := domain.Map{"state": "NOT_OBSERVED"}
	if raw, e := platform.ReadPrivate(filepath.Join(root, "task-drainer.json"), 4096); e == nil {
		if v, e := wire.Decode(raw, 4096); e == nil {
			drainer = v
		}
	}
	checks := domain.Map{"state": "NOT_OBSERVED"}
	if raw, e := platform.ReadPrivate(filepath.Join(root, "task-check-status.json"), 65536); e == nil {
		if v, e := wire.Decode(raw, 65536); e == nil {
			checks = v
		}
	}
	return domain.Map{"checks": checks, "sample_semantics": "LAST_RECORD_NOT_PROCESS_LIVENESS_OR_AUTHENTICATED_HOME_COVERAGE", "drainer": drainer, "clients": clients, "scope": "SUPPORTED_ENGINEERING_INPUTS_ONLY", "clients_scope": "ONLY_SESSIONS_USING_MEMORY_CODEX_ADAPTER", "local_check": localCheck, "raw_transcripts": "NOT_CAPTURED"}
}

func validCursor(v domain.Map) bool {
	last, ok := v["last"].(string)
	return len(v) == 2 && v["schema_version"] == "aevora.task-scan/1" && ok && len(last) <= 255 && (last == "" || filepath.Base(last) == last)
}
func ResetScan(root string) (string, error) {
	path := filepath.Join(root, "task-cursor.json")
	f, e := platform.OpenPrivate(path, os.O_RDONLY)
	if e != nil {
		return "", e
	}
	before, e := f.Stat()
	f.Close()
	if e != nil {
		return "", e
	}
	current, e := os.Lstat(path)
	if e != nil || !os.SameFile(before, current) {
		return "", domain.ErrConflict
	}
	archive := path + ".retained-" + time.Now().UTC().Format("20060102T150405.000000000")
	if _, e = os.Lstat(archive); !os.IsNotExist(e) {
		return "", domain.ErrConflict
	}
	if e = os.Rename(path, archive); e != nil {
		return "", e
	}
	raw, _ := json.Marshal(domain.Map{"schema_version": "aevora.task-scan/1", "last": ""})
	if e = platform.Atomic(path, raw); e != nil {
		return archive, e
	}
	return archive, nil
}
