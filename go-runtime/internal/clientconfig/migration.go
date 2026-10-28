package clientconfig

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"time"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/pelletier/go-toml/v2"
)

// Only our public blocks enter this journal, never the user's config/AGENTS
// files, their digests, environment variables, or session credentials.
type migrationJournal struct {
	Schema, Home, Source, Target, SourceRoot string
	Old, Next                                Receipt
	OldRaw                                   string
	Instructions                             string
	Capture                                  *captureMigration
	Phase                                    string
	Events                                   []migrationEvent
}
type migrationEvent struct{ Phase, At string }
type MigrationResult struct {
	Status    string `json:"status"`
	Journal   string `json:"journal"`
	Reconnect bool   `json:"client_reconnect_required"`
	Authority string `json:"authority"`
	Capture   string `json:"capture"`
	Boundary  string `json:"boundary"`
}

type MigrationFailure struct {
	Journal string
	Cause   error
}

func (e *MigrationFailure) Error() string { return "AEVORA_CLIENT_MIGRATION_INCOMPLETE" }
func (e *MigrationFailure) Unwrap() error { return e.Cause }

func bindingInBlock(block string) (Binding, error) {
	var v map[string]any
	if !strings.HasPrefix(block, begin) || !strings.HasSuffix(block, end) || toml.Unmarshal([]byte(block), &v) != nil || len(v) != 1 {
		return Binding{}, ErrConflict
	}
	servers, ok := v["mcp_servers"].(map[string]any)
	if !ok || len(servers) != 1 {
		return Binding{}, ErrConflict
	}
	server, ok := servers["aevora"].(map[string]any)
	if !ok || len(server) != 2 {
		return Binding{}, ErrConflict
	}
	var b struct {
		Servers map[string]Binding `toml:"mcp_servers"`
	}
	if toml.Unmarshal([]byte(block), &b) != nil {
		return Binding{}, ErrConflict
	}
	return b.Servers["aevora"], nil
}
func managedRoot(b Binding) string {
	if !filepath.IsAbs(b.Command) || len(b.Args) < 3 || b.Args[0] != "mcp-connect" {
		return ""
	}
	root := ""
	seen := map[string]bool{}
	for i := 1; i < len(b.Args); i++ {
		arg := b.Args[i]
		if seen[arg] {
			return ""
		}
		seen[arg] = true
		switch arg {
		case "--session-root", "--run-id":
			if i+1 >= len(b.Args) {
				return ""
			}
			i++
			if arg == "--session-root" {
				root = b.Args[i]
			}
		case "--auto-session", "--route-workspace":
		default:
			return ""
		}
	}
	if !filepath.IsAbs(root) {
		return ""
	}
	return root
}
func ownedBlock(raw []byte, receipt Receipt) bool {
	b, e := bindingInBlock(receipt.Block)
	if e != nil || bytes.Count(raw, []byte(receipt.Block)) != 1 || bytes.Count(raw, []byte(begin)) != 1 || bytes.Count(raw, []byte(end)) != 1 {
		return false
	}
	var v struct {
		Servers map[string]map[string]any `toml:"mcp_servers"`
	}
	if toml.Unmarshal(raw, &v) != nil {
		return false
	}
	var expected struct {
		Servers map[string]map[string]any `toml:"mcp_servers"`
	}
	if toml.Unmarshal([]byte(receipt.Block), &expected) != nil {
		return false
	}
	return managedRoot(b) != "" && reflect.DeepEqual(v.Servers["aevora"], expected.Servers["aevora"])
}
func readReceipt(path, home string) (Receipt, error) {
	var v Receipt
	raw, e := platform.ReadPrivate(path, 4096)
	if e != nil {
		return v, e
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if d.Decode(&v) != nil || v.Schema != "aevora.codex-binding/1" || v.Home != home {
		return v, ErrConflict
	}
	if _, e = bindingInBlock(v.Block); e != nil {
		return v, e
	}
	return v, nil
}
func writeSame(path string, raw []byte, limit int) error {
	old, e := platform.ReadPrivate(path, limit)
	if e == nil {
		if bytes.Equal(old, raw) {
			return nil
		}
		return ErrConflict
	}
	if !os.IsNotExist(e) {
		return e
	}
	return platform.Exclusive(path, raw)
}
func archiveSame(path string, raw []byte, limit int) error {
	if e := writeSame(path+".migrated", raw, limit); e != nil {
		return e
	}
	old, e := platform.ReadPrivate(path, limit)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil {
		return e
	}
	if !bytes.Equal(old, raw) {
		return ErrConflict
	}
	return os.Remove(path)
}

// Migrate commits the config last, after durable target receipts. A crash on
// either side of that commit can be reconciled by the same command. External
// edits are never merged into a stored personal snapshot: only current owned
// blocks are recognized. Undo restores public ownership, not Host authority.
func Migrate(home, source, target, sourceRoot string, next Binding, apply, undo bool) (result MigrationResult, err error) {
	result = MigrationResult{Status: "PREVIEW", Reconnect: true, Authority: "NO_RUN_GRANTS_OR_CREDENTIALS_TRANSFERRED"}
	defer func() {
		if err != nil && apply && result.Journal != "" {
			if _, e := os.Lstat(result.Journal); e == nil {
				err = &MigrationFailure{result.Journal, err}
			}
		}
	}()
	for _, p := range []string{home, source, target} {
		if !filepath.IsAbs(p) {
			return result, ErrConflict
		}
	}
	if source == target || !filepath.IsAbs(sourceRoot) || managedRoot(next) == "" {
		return result, ErrConflict
	}
	if e := platform.PrivateDir(home, false); e != nil {
		return result, e
	}
	if e := platform.PrivateDir(source, false); e != nil {
		return result, e
	}
	if apply {
		if e := platform.PrivateDir(target, true); e != nil {
			return result, e
		}
	}
	paths := []string{filepath.Join(source, "edit.lock"), filepath.Join(source, "instructions.lock"), filepath.Join(source, "capture.lock"), filepath.Join(target, "edit.lock"), filepath.Join(target, "instructions.lock"), filepath.Join(target, "capture.lock")}
	sort.Strings(paths)
	locks := []*os.File{}
	if apply {
		for _, p := range paths {
			f, e := platform.Lock(p)
			if e != nil {
				for _, l := range locks {
					l.Close()
				}
				return result, e
			}
			locks = append(locks, f)
		}
		defer func() {
			for _, f := range locks {
				f.Close()
			}
		}()
	}
	rp, sp := receiptPath(target, home), receiptPath(source, home)
	jp := rp + ".migration"
	result.Journal = jp
	rendered, e := next.TOML()
	if e != nil {
		return result, e
	}
	want := Receipt{Schema: "aevora.codex-binding/1", Home: home, Block: begin + rendered + end}
	j := migrationJournal{}
	old, e := platform.ReadPrivate(jp, 32768)
	if e == nil {
		d := json.NewDecoder(bytes.NewReader(old))
		d.DisallowUnknownFields()
		if d.Decode(&j) != nil || j.Schema != "aevora.connection-migration/1" || j.Home != home || j.Source != source || j.Target != target || j.SourceRoot != sourceRoot || j.Next != want || len(j.Events) > 32 {
			return result, ErrConflict
		}
	} else if os.IsNotExist(e) {
		if undo {
			return result, ErrConflict
		}
		previous, err := readReceipt(sp, home)
		if err != nil {
			return result, err
		}
		binding, err := bindingInBlock(previous.Block)
		if err != nil || managedRoot(binding) != sourceRoot {
			return result, ErrConflict
		}
		if _, err = os.Lstat(rp); !os.IsNotExist(err) {
			return result, ErrConflict
		}
		if _, err = os.Lstat(rp + ".instructions"); !os.IsNotExist(err) {
			return result, ErrConflict
		}
		instructions, err := platform.ReadPrivate(sp+".instructions", 16384)
		if err != nil && !os.IsNotExist(err) {
			return result, err
		}
		if err = CheckInstructions(home, source, false); err != nil {
			return result, err
		}
		rawReceipt, err := platform.ReadPrivate(sp, 4096)
		if err != nil {
			return result, err
		}
		j = migrationJournal{Schema: "aevora.connection-migration/1", Home: home, Source: source, Target: target, SourceRoot: sourceRoot, Old: previous, OldRaw: string(rawReceipt), Next: want, Instructions: string(instructions)}
		j.Capture, err = planCaptureMigration(home, source, target, binding, next)
		if err != nil {
			return result, err
		}
	} else {
		return result, e
	}
	if j.Old.Schema != "aevora.codex-binding/1" || j.Old.Home != home {
		return result, ErrConflict
	}
	var original Receipt
	if json.Unmarshal([]byte(j.OldRaw), &original) != nil || original != j.Old {
		return result, ErrConflict
	}
	previous, e := bindingInBlock(j.Old.Block)
	if e != nil || managedRoot(previous) != sourceRoot {
		return result, ErrConflict
	}
	if e = checkCaptureMigration(home, source, target, j.Capture, previous, next); e != nil {
		return result, e
	}
	result.Capture = "NO_OWNED_HOOK_MIGRATED"
	if j.Capture != nil {
		result.Capture = "OWNED_HOOK_INCLUDED; OFFICIAL_RUNTIME_TRUST_NOT_GRANTED"
	}
	raw, e := readConfig(filepath.Join(home, "config.toml"))
	if e != nil {
		return result, e
	}
	originalConfig := raw
	if normalized, moved, err := normalizeManagedBlock(raw, j.Old); err == nil {
		raw = normalized
		if moved {
			result.Boundary = "OWNED_END_MARKER_RELOCATED; UNRELATED_SETTINGS_PRESERVED"
		}
	} else if normalized, moved, err := normalizeManagedBlock(raw, j.Next); err == nil {
		raw = normalized
		if moved {
			result.Boundary = "OWNED_END_MARKER_RELOCATED; UNRELATED_SETTINGS_PRESERVED"
		}
	}
	oldActive, newActive := ownedBlock(raw, j.Old), ownedBlock(raw, j.Next)
	if !oldActive && !newActive {
		return result, ErrConflict
	}
	for path, want := range map[string]Receipt{sp: j.Old, rp: j.Next} {
		v, e := readReceipt(path, home)
		if e == nil && v != want {
			return result, ErrConflict
		}
		if e != nil && !os.IsNotExist(e) {
			return result, e
		}
	}
	if j.Instructions != "" {
		for _, path := range []string{sp + ".instructions", rp + ".instructions"} {
			v, e := platform.ReadPrivate(path, 16384)
			if e == nil && string(v) != j.Instructions {
				return result, ErrConflict
			}
			if e != nil && !os.IsNotExist(e) {
				return result, e
			}
		}
	}
	if j.Instructions != "" {
		if !strings.HasPrefix(j.Instructions, instructionBegin) || !strings.HasSuffix(j.Instructions, instructionEnd) {
			return result, ErrConflict
		}
		current, e := os.ReadFile(filepath.Join(home, "AGENTS.md"))
		if e != nil || bytes.Count(current, []byte(j.Instructions)) != 1 || bytes.Count(current, []byte(instructionBegin)) != 1 {
			return result, ErrConflict
		}
	}
	if !apply {
		return result, nil
	}
	phase := func(state string) error {
		if j.Phase == state {
			return nil
		}
		j.Phase = state
		j.Events = append(j.Events, migrationEvent{state, time.Now().UTC().Format(time.RFC3339Nano)})
		encoded, e := json.Marshal(j)
		if e != nil {
			return e
		}
		return platform.AtomicLimit(jp, encoded, 32768)
	}
	state := "COMPLETED"
	preparing := "PREPARED"
	if undo {
		state = "ROLLED_BACK"
		preparing = "UNDO_PREPARED"
	}
	if j.Phase != state {
		if len(j.Events) >= 30 {
			return result, ErrConflict
		}
		if e = phase(preparing); e != nil {
			return result, e
		}
	}
	from, to, owner, other := j.Old, j.Next, rp, sp
	if undo {
		from, to, owner, other = j.Next, j.Old, sp, rp
	}
	encoded, _ := json.Marshal(to)
	if undo {
		encoded = []byte(j.OldRaw)
	}
	if e = writeSame(owner, encoded, 4096); e != nil {
		return result, e
	}
	if j.Instructions != "" {
		if e = writeSame(owner+".instructions", []byte(j.Instructions), 16384); e != nil {
			return result, e
		}
	}
	ownerState := target
	otherState := source
	if undo {
		ownerState, otherState = source, target
	}
	if e = commitCaptureMigration(home, ownerState, j.Capture, undo); e != nil {
		return result, e
	}
	nextRaw := raw
	if ownedBlock(raw, from) {
		nextRaw = bytes.Replace(raw, []byte(from.Block), []byte(to.Block), 1)
	}
	if !bytes.Equal(nextRaw, originalConfig) {
		if !ownedBlock(nextRaw, to) {
			return result, ErrConflict
		}
		current, e := readConfig(filepath.Join(home, "config.toml"))
		if e != nil || !bytes.Equal(current, originalConfig) {
			return result, ErrConflict
		}
		if e = platform.AtomicLimit(filepath.Join(home, "config.toml"), nextRaw, 1024*1024); e != nil {
			return result, e
		}
	}
	encoded, _ = json.Marshal(from)
	if !undo {
		encoded = []byte(j.OldRaw)
	}
	// Serialization order from old versions may differ; archive their exact
	// receipt bytes after checking the same public value.
	if v, e := readReceipt(other, home); e == nil {
		if v != from {
			return result, ErrConflict
		}
		encoded, _ = platform.ReadPrivate(other, 4096)
	} else if !os.IsNotExist(e) {
		return result, e
	}
	if e = archiveSame(other, encoded, 4096); e != nil {
		return result, e
	}
	if j.Instructions != "" {
		if e = archiveSame(other+".instructions", []byte(j.Instructions), 16384); e != nil {
			return result, e
		}
	}
	if e = archiveCaptureMigration(home, otherState, j.Capture, undo); e != nil {
		return result, e
	}
	if e = phase(state); e != nil {
		return result, e
	}
	result.Status = state
	return result, nil
}
