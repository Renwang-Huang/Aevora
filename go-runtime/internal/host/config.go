package host

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/retrieval"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
	"regexp"
)

type Profile struct {
	Schema    string                  `json:"schema_version"`
	Retrieval *retrieval.Config       `json:"retrieval,omitempty"`
	Reranker  *retrieval.RerankConfig `json:"reranker,omitempty"`
	Database  struct {
		Host         string `json:"host,omitempty"`
		Port         int    `json:"port,omitempty"`
		Graph        string `json:"graph,omitempty"`
		PasswordFile string `json:"password_file,omitempty"`
		Kind         string `json:"kind,omitempty"`
		Path         string `json:"path,omitempty"`
	} `json:"database"`
	Session struct {
		Root  string          `json:"root"`
		Facts json.RawMessage `json:"public_context"`
	} `json:"session"`
	Console struct {
		Port int `json:"port"`
	} `json:"console"`
}

var validID = regexp.MustCompile(`^[A-Za-z0-9._-]{1,128}$`)
var graphID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$`)
var ownershipHome = platform.OwnershipHome

func exactKeys(v map[string]any, keys ...string) bool {
	if len(v) != len(keys) {
		return false
	}
	for _, key := range keys {
		if _, ok := v[key]; !ok {
			return false
		}
	}
	return true
}

func ProfilePath() string {
	if p := os.Getenv("AEVORA_CONFIG"); p != "" {
		return p
	}
	base := platform.ConfigHome()
	return filepath.Join(base, "aevora", "host.json")
}

func Load(path string) (Profile, error) {
	var p Profile
	if path == "" {
		path = ProfilePath()
	}
	raw, err := platform.ReadPrivate(path, 65536)
	if err != nil {
		return p, errors.New("HOST_CONFIG_REQUIRED")
	}
	v, e := wire.Decode(raw, 65536)
	if e != nil {
		return p, e
	}
	profileKeys := []string{"schema_version", "database", "session", "console"}
	if _, ok := v["retrieval"]; ok {
		profileKeys = append(profileKeys, "retrieval")
		if v["schema_version"] != "aevora.host-config/2" || v["retrieval"] == nil {
			return p, errors.New("HOST_CONFIG_INVALID")
		}
	}
	if _, ok := v["reranker"]; ok {
		profileKeys = append(profileKeys, "reranker")
		if v["schema_version"] != "aevora.host-config/2" || v["reranker"] == nil {
			return p, errors.New("HOST_CONFIG_INVALID")
		}
	}
	if !exactKeys(v, profileKeys...) {
		return p, errors.New("HOST_CONFIG_INVALID")
	}
	databaseKeys := []string{"host", "port", "graph", "password_file"}
	if v["schema_version"] == "aevora.host-config/2" {
		databaseKeys = []string{"kind", "path"}
	}
	for key, keys := range map[string][]string{"database": databaseKeys, "session": {"root", "public_context"}, "console": {"port"}} {
		child, ok := v[key].(map[string]any)
		if !ok || !exactKeys(child, keys...) {
			return p, errors.New("HOST_CONFIG_INVALID")
		}
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if err = d.Decode(&p); err != nil {
		return p, errors.New("HOST_CONFIG_INVALID")
	}
	if p.Retrieval != nil && p.Retrieval.Validate() != nil {
		return p, errors.New("HOST_CONFIG_INVALID")
	}
	if p.Reranker != nil && p.Reranker.Validate() != nil {
		return p, errors.New("HOST_CONFIG_INVALID")
	}
	if !filepath.IsAbs(p.Session.Root) || p.Console.Port < 1024 || p.Console.Port > 65535 {
		return p, errors.New("HOST_CONFIG_INVALID")
	}
	if p.Schema == "aevora.host-config/1" {
		if p.Database.Host != "127.0.0.1" || p.Database.Port < 1024 || p.Database.Port > 65535 || !graphID.MatchString(p.Database.Graph) || !filepath.IsAbs(p.Database.PasswordFile) {
			return p, errors.New("HOST_CONFIG_INVALID")
		}
	} else if p.Schema == "aevora.host-config/2" {
		if p.Database.Kind != "sqlite" || !filepath.IsAbs(p.Database.Path) {
			return p, errors.New("HOST_CONFIG_INVALID")
		}
	} else {
		return p, errors.New("HOST_CONFIG_INVALID")
	}
	if _, err = wire.Decode(p.Session.Facts, 16384); err != nil {
		return p, err
	}
	return p, nil
}

func BackendID(p Profile) string {
	if p.Database.Kind == "sqlite" {
		identity, e := storage.BackendIdentity(p.Database.Path)
		if e != nil {
			return ""
		}
		return identity
	}
	h := sha256.Sum256([]byte(fmt.Sprintf("falkordb/127.0.0.1/%d/%s", p.Database.Port, p.Database.Graph)))
	return hex.EncodeToString(h[:])
}

func RegistryDir(id string) string {
	base := ownershipHome()
	return filepath.Join(base, "aevora", "backends", id)
}

func Own(p Profile) (*os.File, error) {
	id := BackendID(p)
	if id == "" {
		return nil, platform.ErrUnsafe
	}
	dir := RegistryDir(id)
	if err := platform.PrivateDir(dir, true); err != nil {
		return nil, err
	}
	var f *os.File
	var err error
	if p.Database.Kind == "sqlite" {
		f, err = platform.LockData(p.Database.Path)
	} else {
		f, err = platform.Lock(filepath.Join(dir, "writer.lock"))
	}
	if err != nil {
		return nil, err
	}
	root, err := filepath.EvalSymlinks(p.Session.Root)
	if err != nil {
		f.Close()
		return nil, err
	}
	binding := filepath.Join(dir, "binding.json")
	b, _ := json.Marshal(map[string]string{"schema_version": "aevora.backend-binding/1", "root": root, "backend_id": id})
	if err = platform.Exclusive(binding, b); os.IsExist(err) {
		var old map[string]string
		raw, e := platform.ReadPrivate(binding, 4096)
		if e == nil {
			e = json.Unmarshal(raw, &old)
		}
		if e != nil || old["root"] != root || old["backend_id"] != id {
			err = errors.New("AEVORA_BACKEND_ROOT_CONFLICT")
		} else {
			err = nil
		}
	}
	if err != nil {
		f.Close()
		return nil, err
	}
	return f, nil
}

func DefaultDataDir() string { return filepath.Join(platform.DataHome(), "aevora", "data") }

func Scope(p Profile, run string, proposals bool) engine.RunContext {
	return engine.RunContext{BackendID: BackendID(p), WorkspaceID: BackendID(p), RunID: run, Facts: p.Session.Facts, FactsVersion: "public-context/1", FactsSource: "protected_host_profile", Proposals: proposals}
}

// pinRun preserves the trusted Core's canonical context identity across epochs.
func pinRun(p Profile, scope engine.RunContext, binding string) error {
	if len(binding) != 64 {
		return engine.ErrRunContext
	}
	if _, e := hex.DecodeString(binding); e != nil {
		return engine.ErrRunContext
	}
	directory := filepath.Join(p.Session.Root, "contexts")
	if e := platform.PrivateDir(directory, true); e != nil {
		return e
	}
	identity := sha256.Sum256([]byte(scope.RunID))
	path := filepath.Join(directory, hex.EncodeToString(identity[:])+".json")
	value := map[string]any{"schema_version": "aevora.run-authority/1", "run_id": scope.RunID, "backend_id": scope.BackendID, "context_sha256": binding}
	raw, _ := json.Marshal(value)
	if e := platform.Exclusive(path, raw); e == nil {
		return nil
	} else if !os.IsExist(e) {
		return e
	}
	previous, e := platform.ReadPrivate(path, 4096)
	if e != nil {
		return e
	}
	old, e := wire.Decode(previous, 4096)
	if e != nil || len(old) != len(value) {
		return engine.ErrRunContext
	}
	for key, expected := range value {
		if old[key] != expected {
			return engine.ErrRunContext
		}
	}
	return nil
}
