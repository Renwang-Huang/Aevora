package local

import (
	"errors"
	"path/filepath"
	"strings"
)

var ErrProjectNotRegistered = errors.New("AEVORA_PROJECT_NOT_REGISTERED")

// Match the most specific registered workspace. Ambiguous aliases are never
// silently resolved; separate projects retain separate backend capabilities.
func SelectWorkspace(directory string) (Project, error) {
	projects, err := Projects()
	if err != nil {
		return Project{}, err
	}
	return selectWorkspaceAmong(directory, projects)
}

func selectWorkspaceAmong(directory string, projects []Project) (Project, error) {
	real, err := filepath.EvalSymlinks(directory)
	if err != nil {
		return Project{}, err
	}
	var selected Project
	ambiguous := false
	for _, p := range projects {
		rel, err := filepath.Rel(p.Workspace, real)
		if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
			continue
		}
		if len(p.Workspace) > len(selected.Workspace) {
			selected = p
			ambiguous = false
		} else if len(p.Workspace) == len(selected.Workspace) {
			ambiguous = true
		}
	}
	if selected.Name == "" {
		return Project{}, ErrProjectNotRegistered
	}
	if ambiguous {
		return Project{}, errors.New("AEVORA_PROJECT_AMBIGUOUS")
	}
	return selected, nil
}
