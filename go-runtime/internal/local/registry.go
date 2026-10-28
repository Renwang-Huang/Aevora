// Package local stores trusted user's project and task bindings, never credentials.
package local

import (
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/google/uuid"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"time"
)

var ErrInvalid = errors.New("AEVORA_LOCAL_BINDING_INVALID")
var Name = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`)

type Project struct {
	Schema    string `json:"schema_version"`
	Name      string `json:"name"`
	Workspace string `json:"workspace"`
	Profile   string `json:"profile"`
	BackendID string `json:"backend_id"`
}
type Task struct {
	Schema    string          `json:"schema_version"`
	Project   string          `json:"project"`
	Name      string          `json:"name"`
	Run       string          `json:"run_id"`
	Facts     json.RawMessage `json:"facts"`
	Proposals bool            `json:"proposals"`
	Created   string          `json:"created_at"`
	Context   json.RawMessage `json:"context_observation,omitempty"`
}
type TaskState struct {
	Schema    string `json:"schema_version"`
	State     string `json:"state"`
	Observed  string `json:"observed_at"`
	Operation string `json:"operation_id,omitempty"`
}

func Home() string {
	if p := os.Getenv("AEVORA_WORKFLOW_HOME"); p != "" {
		return p
	}
	return filepath.Join(platform.OwnershipHome(), "aevora", "workflow")
}
func directory(parts ...string) (string, error) {
	root := Home()
	if !filepath.IsAbs(root) {
		return "", ErrInvalid
	}
	p := filepath.Join(append([]string{root}, parts...)...)
	if e := platform.PrivateDir(p, true); e != nil {
		return "", e
	}
	return p, nil
}
func ProjectDir(name string) (string, error) {
	if !Name.MatchString(name) {
		return "", ErrInvalid
	}
	return directory("projects", name)
}

// Reads must never create registry entries. In particular, a failed task
// lookup cannot leave an empty task directory that breaks later enumeration.
func existingProjectDir(name string) (string, error) {
	if !Name.MatchString(name) || !filepath.IsAbs(Home()) {
		return "", ErrInvalid
	}
	p := filepath.Join(Home(), "projects", name)
	if err := platform.PrivateDir(p, false); err != nil {
		return "", err
	}
	return p, nil
}
func read(path string, v any) error {
	limit := recordLimit(v)
	raw, e := platform.ReadPrivate(path, limit)
	if e != nil {
		return e
	}
	if _, e = wire.Decode(raw, limit); e != nil {
		return e
	}
	return json.Unmarshal(raw, v)
}
func write(path string, v any, replace bool) error {
	raw, e := json.Marshal(v)
	if e != nil || len(raw) > recordLimit(v) {
		return ErrInvalid
	}
	if replace {
		return platform.Atomic(path, raw)
	}
	return platform.Exclusive(path, raw)
}

func recordLimit(v any) int {
	switch v.(type) {
	case Task, *Task:
		return 65536
	default:
		return 4096
	}
}
func Register(p Project) error {
	dir, e := ProjectDir(p.Name)
	if e != nil {
		return e
	}
	if p.Schema != "aevora.local-project/1" || !filepath.IsAbs(p.Profile) || !filepath.IsAbs(p.Workspace) || len(p.BackendID) != 64 {
		return ErrInvalid
	}
	real, e := filepath.EvalSymlinks(p.Workspace)
	if e != nil || real != p.Workspace {
		return ErrInvalid
	}
	return write(filepath.Join(dir, "project.json"), p, false)
}
func Load(name string) (Project, error) {
	var p Project
	dir, e := existingProjectDir(name)
	if e != nil {
		return p, e
	}
	e = read(filepath.Join(dir, "project.json"), &p)
	if e != nil {
		return p, e
	}
	if p.Schema != "aevora.local-project/1" || p.Name != name || !filepath.IsAbs(p.Profile) || !filepath.IsAbs(p.Workspace) || len(p.BackendID) != 64 {
		return p, ErrInvalid
	}
	return p, nil
}
func Projects() ([]Project, error) {
	dir, e := directory("projects")
	if e != nil {
		return nil, e
	}
	entries, e := os.ReadDir(dir)
	if e != nil || len(entries) > 256 {
		return nil, ErrInvalid
	}
	out := []Project{}
	for _, entry := range entries {
		if !entry.IsDir() || !Name.MatchString(entry.Name()) {
			return nil, ErrInvalid
		}
		p, e := Load(entry.Name())
		if os.IsNotExist(e) {
			continue
		}
		if e != nil {
			return nil, e
		}
		out = append(out, p)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out, nil
}
func taskDir(project, name string) (string, error) {
	if !Name.MatchString(name) {
		return "", ErrInvalid
	}
	dir, e := ProjectDir(project)
	if e != nil {
		return "", e
	}
	p := filepath.Join(dir, "tasks", name)
	if e = platform.PrivateDir(p, true); e != nil {
		return "", e
	}
	return p, nil
}
func NewTask(p Project, name string, facts json.RawMessage, proposals bool) (Task, error) {
	return NewObservedTask(p, name, facts, nil, proposals)
}
func NewObservedTask(p Project, name string, facts, observation json.RawMessage, proposals bool) (Task, error) {
	t := Task{Schema: "aevora.local-task/1", Project: p.Name, Name: name, Run: "task-" + uuid.NewString(), Facts: facts, Proposals: proposals, Created: time.Now().UTC().Format(time.RFC3339Nano)}
	t.Context = observation
	if _, e := wire.Decode(facts, 16384); e != nil {
		return t, e
	}
	dir, e := taskDir(p.Name, name)
	if e != nil {
		return t, e
	}
	if e = write(filepath.Join(dir, "task.json"), t, false); e != nil {
		return t, e
	}
	return t, SetState(t, "PREPARED", "")
}
func LoadTask(project, name string) (Task, TaskState, error) {
	var t Task
	var s TaskState
	if !Name.MatchString(name) {
		return t, s, ErrInvalid
	}
	projectDir, e := existingProjectDir(project)
	if os.IsNotExist(e) {
		return t, s, errors.New("AEVORA_TASK_NOT_FOUND")
	}
	if e != nil {
		return t, s, e
	}
	dir := filepath.Join(projectDir, "tasks", name)
	if e = read(filepath.Join(dir, "task.json"), &t); e != nil {
		if os.IsNotExist(e) {
			e = errors.New("AEVORA_TASK_NOT_FOUND")
		}
		return t, s, e
	}
	if t.Schema != "aevora.local-task/1" || t.Project != project || t.Name != name || !Name.MatchString(t.Run) {
		return t, s, ErrInvalid
	}
	if e = read(filepath.Join(dir, "state.json"), &s); e != nil {
		return t, s, e
	}
	if s.Schema != "aevora.local-task-state/1" {
		return t, s, ErrInvalid
	}
	return t, s, nil
}
func SetState(t Task, state, operation string) error {
	switch state {
	case "PREPARED", "AUTHORIZATION_UNKNOWN", "AUTHORIZED", "CLOSED", "INTERRUPTED", "CLIENT_EXITED", "FAILED":
	default:
		return ErrInvalid
	}
	dir, e := taskDir(t.Project, t.Name)
	if e != nil {
		return e
	}
	return write(filepath.Join(dir, "state.json"), TaskState{Schema: "aevora.local-task-state/1", State: state, Observed: time.Now().UTC().Format(time.RFC3339Nano), Operation: operation}, true)
}
func Tasks(project string) ([]map[string]any, error) {
	dir, e := existingProjectDir(project)
	if e != nil {
		return nil, e
	}
	entries, e := os.ReadDir(filepath.Join(dir, "tasks"))
	if os.IsNotExist(e) {
		return []map[string]any{}, nil
	}
	if e != nil || len(entries) > 4096 {
		return nil, ErrInvalid
	}
	out := []map[string]any{}
	for _, v := range entries {
		t, s, e := LoadTask(project, v.Name())
		if e != nil {
			return nil, e
		}
		out = append(out, map[string]any{"task": t, "status": s})
	}
	return out, nil
}
