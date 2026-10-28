package local

import (
	"path/filepath"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
)

// The public owner policy bounds routing hints, not authorization. The Host
// still authenticates the capability and checks backend, registration and
// current allowlist independently. Old aliases on other backends cannot make
// an otherwise authorized restored route ambiguous.
func SelectAutomaticWorkspace(root, directory string) (Project, error) {
	raw, e := platform.ReadPrivate(filepath.Join(root, "automatic-policy.json"), 4096)
	if e != nil {
		return Project{}, e
	}
	v, e := wire.Decode(raw, 4096)
	if e != nil {
		return Project{}, e
	}
	for k := range v {
		if k != "project" && k != "workspace" && k != "proposals" && k != "routes" {
			return Project{}, ErrInvalid
		}
	}
	if _, ok := v["proposals"].(bool); !ok {
		return Project{}, ErrInvalid
	}
	routes := []map[string]any{v}
	if extra, ok := v["routes"]; ok {
		items, ok := extra.([]any)
		if !ok || len(items) > 64 {
			return Project{}, ErrInvalid
		}
		for _, item := range items {
			m, ok := item.(map[string]any)
			if !ok || len(m) != 2 {
				return Project{}, ErrInvalid
			}
			routes = append(routes, m)
		}
	}
	projects := []Project{}
	seen := map[string]bool{}
	for _, route := range routes {
		name, ok := route["project"].(string)
		workspace, wok := route["workspace"].(string)
		if !ok || !wok || seen[name] {
			return Project{}, ErrInvalid
		}
		seen[name] = true
		p, e := Load(name)
		if e != nil {
			return Project{}, e
		}
		if p.Workspace != workspace {
			return Project{}, ErrInvalid
		}
		projects = append(projects, p)
	}
	return selectWorkspaceAmong(directory, projects)
}
