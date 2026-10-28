// Package clientconfig renders scoped bindings and edits only a managed MCP block.
package clientconfig

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/pelletier/go-toml/v2"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"time"
)

var ErrConflict = errors.New("AEVORA_CLIENT_CONFIG_CONFLICT")

type Binding struct {
	Command string   `json:"command" toml:"command"`
	Args    []string `json:"args" toml:"args"`
}

func New(binary, root, run string) Binding {
	return Binding{binary, []string{"mcp-connect", "--session-root", root, "--run-id", run}}
}
func Automatic(binary, root string) Binding {
	return Binding{binary, []string{"mcp-connect", "--session-root", root, "--auto-session"}}
}
func AutomaticWorkspace(binary, root string) Binding {
	b := Automatic(binary, root)
	b.Args = append(b.Args, "--route-workspace")
	return b
}
func (b Binding) TOML() (string, error) {
	v, e := toml.Marshal(map[string]any{"mcp_servers": map[string]any{"aevora": b}})
	return string(v), e
}

// JSON strings and arrays are valid TOML values. Replacing the whole inline table
// prevents a stored HTTP/url transport from surviving a per-invocation override.
func (b Binding) Override() string {
	command, _ := json.Marshal(b.Command)
	args, _ := json.Marshal(b.Args)
	return "mcp_servers.aevora={command=" + string(command) + ",args=" + string(args) + ",enabled=true}"
}

// OverridesBinding checks parsed TOML keys, including quoted or spaced table
// names, so forwarded CLI options cannot silently replace the fixed task MCP.
func OverridesBinding(args []string) bool {
	for i, arg := range args {
		var value string
		switch {
		case arg == "--ignore-user-config":
			return true
		case arg == "-c" || arg == "--config":
			if i+1 >= len(args) {
				return true
			}
			value = args[i+1]
		case strings.HasPrefix(arg, "--config="):
			value = strings.TrimPrefix(arg, "--config=")
		case strings.HasPrefix(arg, "-c") && len(arg) > 2:
			value = arg[2:]
		default:
			continue
		}
		key, _, ok := strings.Cut(value, "=")
		var parsed map[string]any
		if !ok || toml.Unmarshal([]byte(key+" = 0"), &parsed) != nil {
			return true
		}
		if _, exists := parsed["mcp_servers"]; exists {
			return true
		}
	}
	return false
}

type limitBuffer struct{ bytes.Buffer }

func (b *limitBuffer) Write(p []byte) (int, error) {
	if b.Len()+len(p) > 65536 {
		return 0, ErrConflict
	}
	return b.Buffer.Write(p)
}
func Probe(ctx context.Context, executable string, b Binding, homes ...string) (map[string]any, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, executable, "-c", b.Override(), "mcp", "get", "aevora", "--json")
	var out, stderr limitBuffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr
	cmd.WaitDelay = time.Second
	if len(homes) > 0 && homes[0] != "" {
		cmd.Env = append(os.Environ(), "CODEX_HOME="+homes[0])
	}
	if e := cmd.Run(); e != nil {
		return nil, errors.New("AEVORA_CLIENT_CONFIG_CHECK_FAILED")
	}
	var v struct {
		Transport struct {
			Type    string   `json:"type"`
			Command string   `json:"command"`
			Args    []string `json:"args"`
		} `json:"transport"`
	}
	if e := json.Unmarshal(out.Bytes(), &v); e != nil {
		return nil, ErrConflict
	}
	x, _ := json.Marshal(v.Transport.Args)
	y, _ := json.Marshal(b.Args)
	if v.Transport.Type != "stdio" || v.Transport.Command != b.Command || !bytes.Equal(x, y) {
		return nil, ErrConflict
	}
	return map[string]any{"status": "CONFIG_PARSED", "client": "codex", "transport": "stdio", "actual_agent_tool_call": "NOT_PROVEN", "personal_config": "NOT_MODIFIED"}, nil
}

const begin = "\n# Aevora managed MCP binding BEGIN\n"
const end = "# Aevora managed MCP binding END\n"

type Receipt struct {
	Schema string `json:"schema_version"`
	Home   string `json:"home"`
	Block  string `json:"block"`
}

func receiptPath(state, home string) string {
	h := sha256.Sum256([]byte(home))
	return filepath.Join(state, "codex-"+hex.EncodeToString(h[:16])+".json")
}
func readConfig(path string) ([]byte, error) {
	f, e := platform.OpenPrivate(path, os.O_RDONLY)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	before, e := f.Stat()
	if e != nil || before.Size() > 1024*1024 {
		return nil, ErrConflict
	}
	raw, e := io.ReadAll(io.LimitReader(f, 1024*1024+1))
	after, aerr := f.Stat()
	if e != nil || aerr != nil || int64(len(raw)) != before.Size() || before.Size() != after.Size() || before.ModTime() != after.ModTime() {
		return nil, ErrConflict
	}
	return raw, nil
}

// Apply preserves all bytes outside its own block. No personal configuration or
// credential digest is saved; the undo receipt contains only our scoped binding.
func Apply(home, state string, b Binding, remove bool) (string, error) {
	if !filepath.IsAbs(home) || !filepath.IsAbs(state) {
		return "", ErrConflict
	}
	if e := platform.PrivateDir(home, true); e != nil {
		return "", e
	}
	if e := platform.PrivateDir(state, true); e != nil {
		return "", e
	}
	lock, e := platform.Lock(filepath.Join(state, "edit.lock"))
	if e != nil {
		return "", e
	}
	defer lock.Close()
	path := filepath.Join(home, "config.toml")
	raw, e := readConfig(path)
	if os.IsNotExist(e) {
		raw = nil
	} else if e != nil {
		return "", e
	}
	var parsed map[string]any
	if e = toml.Unmarshal(raw, &parsed); e != nil {
		return "", ErrConflict
	}
	receipt := Receipt{}
	rp := receiptPath(state, home)
	old, e := platform.ReadPrivate(rp, 4096)
	owned := e == nil
	if owned {
		if json.Unmarshal(old, &receipt) != nil || receipt.Schema != "aevora.codex-binding/1" || receipt.Home != home {
			return "", ErrConflict
		}
	} else if !os.IsNotExist(e) {
		return "", e
	}
	remaining := raw
	if owned {
		normalized, _, err := normalizeManagedBlock(raw, receipt)
		if err != nil {
			return "", err
		}
		var expected map[string]any
		if toml.Unmarshal([]byte(receipt.Block), &expected) != nil {
			return "", ErrConflict
		}
		actualServers, _ := parsed["mcp_servers"].(map[string]any)
		expectedServers, _ := expected["mcp_servers"].(map[string]any)
		if !reflect.DeepEqual(actualServers["aevora"], expectedServers["aevora"]) {
			return "", ErrConflict
		}
		remaining = bytes.Replace(normalized, []byte(receipt.Block), nil, 1)
	} else {
		servers, _ := parsed["mcp_servers"].(map[string]any)
		if _, exists := servers["aevora"]; exists {
			return "", ErrConflict
		}
		if bytes.Contains(raw, []byte(begin)) || bytes.Contains(raw, []byte(end)) {
			return "", ErrConflict
		}
	}
	if remove && !owned {
		return "UNCHANGED", nil
	}
	block := ""
	if !remove {
		rendered, e := b.TOML()
		if e != nil {
			return "", e
		}
		block = begin + rendered + end
	}
	next := append(append([]byte{}, remaining...), []byte(block)...)
	var verified map[string]any
	if toml.Unmarshal(next, &verified) != nil {
		return "", ErrConflict
	}
	// Detect external edits immediately before atomic replacement. Other config
	// writers need not understand our lock; their observed changes cause refusal.
	current, e := readConfig(path)
	if e != nil && !os.IsNotExist(e) {
		return "", e
	}
	if !bytes.Equal(raw, current) {
		return "", ErrConflict
	}
	if !bytes.Equal(raw, next) {
		if e = platform.AtomicLimit(path, next, 1024*1024); e != nil {
			return "", e
		}
	}
	if remove {
		if e = os.Remove(rp); e != nil {
			return "", e
		}
		return "REMOVED", nil
	}
	receipt = Receipt{Schema: "aevora.codex-binding/1", Home: home, Block: block}
	encoded, _ := json.Marshal(receipt)
	if e = platform.Atomic(rp, encoded); e != nil {
		return "", e
	}
	return "APPLIED", nil
}
