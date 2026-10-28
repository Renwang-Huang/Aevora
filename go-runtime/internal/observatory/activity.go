package observatory

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"io"
	"os"
	"path/filepath"
	"sort"
)

func RuntimeHeaders(directories func() []string) func() ([]Map, error) {
	return func() ([]Map, error) {
		dirs := directories()
		sort.Strings(dirs)
		if len(dirs) > 64 {
			return nil, domain.ErrInvalid
		}
		out := []Map{}
		for _, directory := range dirs {
			raw, e := platform.ReadPrivate(filepath.Join(directory, "session.json"), 4096)
			if e != nil {
				return nil, e
			}
			header, e := wire.Decode(raw, 4096)
			if e != nil {
				return nil, e
			}
			run := domain.S(header["run_id"])
			if header["schema_version"] != "aevora.local-session/1" || !storage.ValidID(run) {
				return nil, domain.ErrInvalid
			}
			f, e := platform.OpenPrivate(filepath.Join(directory, "mcp_events.jsonl"), os.O_RDONLY)
			if e != nil {
				return nil, e
			}
			data, e := io.ReadAll(io.LimitReader(f, 128*1024+1))
			f.Close()
			if e != nil {
				return nil, e
			}
			stream := "COMPLETE_OBSERVED_PREFIX"
			if len(data) > 128*1024 {
				data = data[:128*1024]
				stream = "BOUNDED_PREFIX_NOT_COMPLETE"
			}
			end := bytes.LastIndexByte(data, '\n')
			if end < len(data)-1 && stream == "COMPLETE_OBSERVED_PREFIX" {
				stream = "PARTIAL_INCOMPLETE_TAIL"
			}
			data = data[:end+1]
			scanner := bufio.NewScanner(bytes.NewReader(data))
			scanner.Buffer(make([]byte, 8192), 8192)
			events := []any{}
			line := 0
			observed := any(nil)
			for scanner.Scan() {
				line++
				raw := scanner.Bytes()
				event, e := wire.Decode(raw, 8192)
				if e != nil {
					return nil, e
				}
				if event["schema_version"] != "aevora.runtime-event/1" || event["source"] != "aevora.native_host" || event["run_id"] != run {
					return nil, domain.ErrInvalid
				}
				observed = event["timestamp"]
				category := domain.S(event["category"])
				if category != "resolve_experience" && category != "build_evidence_bundle" && category != "record_decision" && category != "propose_experience" {
					continue
				}
				hash := sha256.Sum256(append(append([]byte{}, raw...), '\n'))
				events = append(events, Map{"tool": category, "timestamp": event["timestamp"], "line": line, "line_sha256": hex.EncodeToString(hash[:]), "source_artifact": "OWNER_CONFIGURED_CORE_MCP_LOG", "operation_id": event["operation_id"], "operation_state": event["state"], "source_kind": "NATIVE_HOST_OPERATION_METADATA"})
				if len(events) > 100 {
					events = events[1:]
				}
			}
			if err := scanner.Err(); err != nil {
				return nil, err
			}
			if len(events) == 0 {
				continue
			}
			out = append(out, Map{"run_id": run, "session_id": nil, "status": "HOST_CHANNEL_OBSERVED", "source": "ACTUAL_OWNER_CONFIGURED_CORE_CHANNEL", "authority": "EXTERNAL_UNVERIFIED", "header_observed_at": observed, "process_liveness": "UNAVAILABLE_NOT_PROBED", "tool_events": events, "event_stream_status": stream, "native_identity": "UNAVAILABLE; channel metadata is not native Runtime proof"})
		}
		return out, nil
	}
}
