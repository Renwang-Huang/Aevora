package host

import (
	"bufio"
	"bytes"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// OperationStatus inspects protected metadata; it never retries business work.
func OperationStatus(directory, id string) (map[string]any, error) {
	if len(id) != 64 {
		return nil, wire.ErrInvalid
	}
	if _, e := hex.DecodeString(id); e != nil {
		return nil, e
	}
	raw, e := platform.ReadPrivate(filepath.Join(directory, "mcp_events.jsonl"), 32*1024*1024)
	if e != nil {
		return nil, e
	}
	if end := bytes.LastIndexByte(raw, '\n'); end >= 0 {
		raw = raw[:end+1]
	} else {
		return nil, errors.New("AEVORA_OPERATION_NOT_FOUND")
	}
	scanner := bufio.NewScanner(bytes.NewReader(raw))
	scanner.Buffer(make([]byte, 4096), 8192)
	state := ""
	run := ""
	written := false
	for scanner.Scan() {
		v, e := wire.Decode(scanner.Bytes(), 8192)
		if e != nil {
			return nil, e
		}
		if v["schema_version"] != "aevora.runtime-event/1" || v["source"] != "aevora.native_host" {
			return nil, wire.ErrInvalid
		}
		if v["operation_id"] != id {
			continue
		}
		run, _ = v["run_id"].(string)
		if v["category"] == "RESPONSE" || v["category"] == "MANAGEMENT_RESPONSE" {
			written = v["state"] == "WRITTEN_TO_TRANSPORT"
		} else {
			state, _ = v["state"].(string)
		}
	}
	if e := scanner.Err(); e != nil {
		return nil, e
	}
	if state == "" {
		return nil, errors.New("AEVORA_OPERATION_NOT_FOUND")
	}
	if state == "DISPATCHED" {
		state = "UNKNOWN"
	}
	return map[string]any{"operation_id": id, "run_id": run, "state": state, "response_written_to_transport": written, "database_persistence": "NOT_CONFIRMED", "automatic_replay": false}, nil
}

// Journal contains metadata only. It is not a database commit receipt.
type Journal struct {
	mu       sync.Mutex
	file     *os.File
	size     int
	sequence int
	run      string
}

func newJournal(path, run string) (*Journal, error) {
	f, e := platform.OpenPrivate(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL)
	if e != nil {
		return nil, e
	}
	return &Journal{file: f, run: run}, nil
}

func (j *Journal) Event(category, session, operation, state string) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	if j.file == nil {
		return errors.New("AEVORA_AUDIT_CLOSED")
	}
	j.sequence++
	v := map[string]any{"schema_version": "aevora.runtime-event/1", "source": "aevora.native_host", "run_id": j.run, "sequence": j.sequence, "timestamp": time.Now().UTC().Format(time.RFC3339Nano), "category": category, "session_id": session, "operation_id": operation, "state": state}
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	b = append(b, '\n')
	if j.size+len(b) > 32*1024*1024 {
		return errors.New("AEVORA_AUDIT_LIMIT")
	}
	n, e := j.file.Write(b)
	j.size += n
	if e == nil && n != len(b) {
		return errors.New("AEVORA_AUDIT_WRITE_FAILED")
	}
	if e == nil {
		e = j.file.Sync()
	}
	return e
}
func (j *Journal) Bytes() int { j.mu.Lock(); defer j.mu.Unlock(); return j.size }
func (j *Journal) Close() error {
	j.mu.Lock()
	defer j.mu.Unlock()
	if j.file == nil {
		return nil
	}
	e := j.file.Close()
	j.file = nil
	return e
}
