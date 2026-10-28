package host

import (
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/buildinfo"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// RuntimeStatus is bounded, non-secret observation, not a commit or Agent receipt.
type RuntimeStatus struct {
	Schema    string         `json:"schema_version"`
	Backend   string         `json:"backend_id"`
	Epoch     string         `json:"epoch"`
	PID       int            `json:"pid"`
	State     string         `json:"state"`
	Observed  string         `json:"observed_at"`
	Console   string         `json:"console"`
	Run       string         `json:"run_id"`
	Budget    map[string]int `json:"budget"`
	ToolCalls int            `json:"tool_calls_observed"`
	Version   string         `json:"version"`
	Revision  string         `json:"revision"`
	Warnings  []string       `json:"warnings"`
	Capture   CaptureStatus  `json:"capture"`
}

func budgetWarnings(b map[string]int) []string {
	out := []string{}
	for _, metric := range [][3]string{
		{"consumer_connections", "consumer_connection_limit", "CONSUMER_CONNECTIONS"},
		{"frames", "frame_limit", "PROTOCOL_FRAMES"},
		{"consumer_nonces", "consumer_nonce_limit", "CONSUMER_AUTH"},
		{"management_nonces", "management_nonce_limit", "MANAGEMENT_AUTH"},
		{"runs_total", "run_limit", "DISTINCT_RUNS"},
		{"largest_current_journal_bytes", "journal_bytes_limit", "CURRENT_JOURNAL"},
	} {
		used, limit := b[metric[0]], b[metric[1]]
		if limit > 0 && used >= limit {
			out = append(out, metric[2]+"_EXHAUSTED")
		} else if limit > 0 && used >= (limit*85+99)/100 {
			out = append(out, metric[2]+"_LOW")
		}
	}
	return out
}

func (h *Host) Snapshot() RuntimeStatus {
	h.mu.Lock()
	defer h.mu.Unlock()
	active, connections, journalBytes, largestJournal := 0, 0, 0, 0
	for _, a := range h.runs {
		if a.journal != nil {
			n := a.journal.Bytes()
			journalBytes += n
			if n > largestJournal {
				largestJournal = n
			}
		}
		if !a.revoked {
			active++
		}
	}
	for name := range h.sessions {
		if !strings.HasPrefix(name, "management-") {
			connections++
		}
	}
	result := RuntimeStatus{Version: buildinfo.Version, Revision: buildinfo.Revision, Schema: "aevora.runtime-status/1", Backend: h.scope.BackendID, Epoch: filepath.Base(h.folder), PID: os.Getpid(), State: h.runtimeState, Observed: time.Now().UTC().Format(time.RFC3339Nano), Console: h.consoleURL, Run: h.scope.RunID, ToolCalls: h.toolCalls, Capture: h.captureStatus, Budget: map[string]int{"consumer_connections": connections, "consumer_connection_limit": 4, "frames": h.frames, "frame_limit": 4096, "consumer_nonces": len(h.nonces), "consumer_nonce_limit": 4096, "management_nonces": len(h.managementNonces), "management_nonce_limit": 1024, "runs_total": len(h.runs), "runs_active": active, "run_limit": 64, "current_journals_bytes": journalBytes, "largest_current_journal_bytes": largestJournal, "journal_bytes_limit": 32 * 1024 * 1024}}
	result.Warnings = budgetWarnings(result.Budget)
	if h.captureStatus.State != "" && h.captureStatus.State != "DRAINER_READY" {
		result.Warnings = append(result.Warnings, "CAPTURE_"+h.captureStatus.State)
	}
	return result
}
func (h *Host) publishStatus() error {
	raw, e := json.Marshal(h.Snapshot())
	if e != nil {
		return e
	}
	return platform.Atomic(filepath.Join(RegistryDir(h.scope.BackendID), "runtime.json"), raw)
}
func (h *Host) startStatus() error {
	h.mu.Lock()
	h.runtimeState = "STARTING"
	h.mu.Unlock()
	if e := h.publishStatus(); e != nil {
		return e
	}
	h.wg.Add(1)
	go func() {
		defer h.wg.Done()
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-h.stopContext.Done():
				return
			case <-ticker.C:
				if e := h.publishStatus(); e != nil {
					h.mu.Lock()
					h.statusErr = errors.New("AEVORA_STATUS_WRITE_FAILED")
					h.mu.Unlock()
					h.stopConnections()
					return
				}
			}
		}
	}()
	return nil
}
func (h *Host) Ready(console string) error {
	h.mu.Lock()
	h.consoleURL = console
	h.runtimeState = "READY"
	h.mu.Unlock()
	return h.publishStatus()
}
func ReadStatus(p Profile) (RuntimeStatus, error) {
	var s RuntimeStatus
	raw, e := platform.ReadPrivate(filepath.Join(RegistryDir(BackendID(p)), "runtime.json"), 4096)
	if e != nil {
		return s, e
	}
	if e = json.Unmarshal(raw, &s); e != nil {
		return s, e
	}
	when, e := time.Parse(time.RFC3339Nano, s.Observed)
	if e != nil || s.Schema != "aevora.runtime-status/1" || s.Backend != BackendID(p) || !directoryID.MatchString(s.Epoch) || s.PID < 1 || time.Since(when) > 20*time.Second || time.Until(when) > 5*time.Second {
		return s, errors.New("AEVORA_RUNTIME_STATUS_STALE")
	}
	if p.Database.Kind == "sqlite" && s.Console != "" {
		u, e := url.Parse(s.Console)
		if e != nil || u.Scheme != "http" || u.Hostname() != "127.0.0.1" || u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" {
			return s, errors.New("AEVORA_RUNTIME_STATUS_STALE")
		}
		port, e := strconv.Atoi(u.Port())
		if e != nil || port < 1024 || port > 65535 {
			return s, errors.New("AEVORA_RUNTIME_STATUS_STALE")
		}
	}
	return s, nil
}
