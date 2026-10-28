package local

import (
	"bytes"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/pelletier/go-toml/v2"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

func observeWorktree(root string, git func(...string) (string, error)) (domain.Map, error) {
	raw, err := git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")
	if err != nil {
		return nil, err
	}
	items := strings.Split(raw, "\x00")
	entries := []any{}
	state := "CLEAN"
	for i := 0; i < len(items); i++ {
		line := items[i]
		if line == "" {
			continue
		}
		if len(line) < 4 || len(entries) >= 2048 {
			return nil, ErrInvalid
		}
		code, path := line[:2], line[3:]
		clean := filepath.Clean(path)
		if filepath.IsAbs(clean) || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
			return nil, ErrInvalid
		}
		full := filepath.Join(root, clean)
		// Never inspect through an intermediate symlink outside the workspace.
		parent, e := filepath.EvalSymlinks(filepath.Dir(full))
		if e != nil || parent != root && !strings.HasPrefix(parent, root+string(filepath.Separator)) {
			return nil, ErrInvalid
		}
		info, e := os.Lstat(full)
		entry := domain.Map{"status": code, "path": path}
		if e == nil {
			entry["size"] = info.Size()
			entry["mtime_ns"] = info.ModTime().UnixNano()
			entry["mode"] = uint64(info.Mode())
		} else if !os.IsNotExist(e) {
			return nil, e
		} else {
			entry["missing"] = true
		}
		if strings.ContainsAny(code, "RC") {
			i++
			if i >= len(items) || items[i] == "" {
				return nil, ErrInvalid
			}
			entry["original_path"] = items[i]
		}
		if code == "UU" || code == "AA" || code == "DD" || strings.Contains(code, "U") {
			state = "CONFLICTED"
		} else if state == "CLEAN" {
			state = "DIRTY"
		}
		entries = append(entries, entry)
	}
	index, err := git("diff", "--cached", "--raw", "--no-abbrev", "--no-renames", "--no-ext-diff", "--no-textconv", "HEAD")
	if err != nil {
		return nil, err
	}
	snapshot, err := codec.Digest(domain.Map{"git_status_and_file_metadata": entries, "index_changes": index})
	if err != nil {
		return nil, err
	}
	return domain.Map{"target_worktree_state": state, "target_worktree_snapshot": snapshot}, nil
}

var requirement = regexp.MustCompile(`^[0-9.<>=|^~*+,! xX-]{1,80}$`)
var goDirective = regexp.MustCompile(`(?m)^go[ \t]+([0-9]+\.[0-9]+(?:\.[0-9]+)?)\s*$`)

// Probe only the registered root and immediate source module directories.
// No recursive workspace resolver, vendor tree, hidden directory or symlink
// traversal. Discovery limits fall back to an explicitly root-only scope.
func manifestPaths(root string, names []string) ([]string, string) {
	paths := append([]string{}, names...)
	dir, err := os.Open(root)
	if err != nil {
		return paths, "ROOT_ONLY_MODULE_DISCOVERY_UNAVAILABLE"
	}
	entries, err := dir.ReadDir(257)
	dir.Close()
	if err != nil && err != io.EOF {
		return paths, "ROOT_ONLY_MODULE_DISCOVERY_UNAVAILABLE"
	}
	if len(entries) > 256 {
		return paths, "ROOT_ONLY_CHILD_ENTRY_LIMIT"
	}
	excluded := map[string]bool{"node_modules": true, "vendor": true, "build": true, "dist": true, "target": true, "__pycache__": true, "venv": true, "env": true}
	dirs := []string{}
	for _, entry := range entries {
		if entry.IsDir() && !strings.HasPrefix(entry.Name(), ".") && !excluded[entry.Name()] {
			dirs = append(dirs, entry.Name())
		}
	}
	if len(dirs) > 64 {
		return paths, "ROOT_ONLY_MODULE_DIRECTORY_LIMIT"
	}
	sort.Strings(dirs)
	for _, child := range dirs {
		for _, name := range names {
			paths = append(paths, filepath.Join(child, name))
		}
	}
	return paths, "REGISTERED_ROOT_AND_IMMEDIATE_MODULES"
}

func observeManifests(root string) (domain.Map, string) {
	names := map[string]string{"go.mod": "go", "go.sum": "go", "package.json": "npm", "package-lock.json": "npm", "pnpm-lock.yaml": "npm", "yarn.lock": "npm", "pyproject.toml": "python", "poetry.lock": "python", "uv.lock": "python", "requirements.txt": "python", "Cargo.toml": "cargo", "Cargo.lock": "cargo", "CMakeLists.txt": "cmake", "pom.xml": "maven", "build.gradle": "gradle"}
	files := []string{}
	for name := range names {
		files = append(files, name)
	}
	sort.Strings(files)
	files, coverage := manifestPaths(root, files)
	kinds := map[string]bool{}
	hashes := domain.Map{}
	facts := domain.Map{}
	declarations := map[string]map[string]bool{}
	note := func(key, value string) {
		if declarations[key] == nil {
			declarations[key] = map[string]bool{}
		}
		declarations[key][value] = true
	}
	total := int64(0)
	for _, name := range files {
		path := filepath.Join(root, name)
		// Immediate module parents may change while observing; do not follow a
		// directory symlink into a different workspace.
		real, resolveErr := filepath.EvalSymlinks(path)
		if resolveErr != nil && !os.IsNotExist(resolveErr) {
			return domain.Map{}, "UNAVAILABLE_OR_LIMITED"
		}
		if resolveErr == nil && real != path {
			return domain.Map{}, "UNAVAILABLE_OR_LIMITED"
		}
		before, e := os.Lstat(path)
		if os.IsNotExist(e) {
			continue
		}
		if e != nil || !before.Mode().IsRegular() || before.Size() > 1024*1024 {
			return domain.Map{}, "UNAVAILABLE_OR_LIMITED"
		}
		f, e := os.Open(path)
		if e != nil {
			return domain.Map{}, "UNAVAILABLE_OR_LIMITED"
		}
		actual, e := f.Stat()
		if e != nil || !os.SameFile(before, actual) {
			f.Close()
			return domain.Map{}, "CHANGED_DURING_OBSERVATION"
		}
		data, e := io.ReadAll(io.LimitReader(f, 1024*1024+1))
		after, statErr := f.Stat()
		f.Close()
		current, pathErr := os.Lstat(path)
		finalReal, resolveErr := filepath.EvalSymlinks(path)
		total += int64(len(data))
		if e != nil || statErr != nil || pathErr != nil || resolveErr != nil || finalReal != path || !os.SameFile(before, current) || before.Size() != after.Size() || !before.ModTime().Equal(after.ModTime()) || len(data) > 1024*1024 || total > 4*1024*1024 {
			return domain.Map{}, "UNAVAILABLE_OR_LIMITED"
		}
		hashes[name] = domain.BytesSHA(data)
		baseName := filepath.Base(name)
		kinds[names[baseName]] = true
		switch baseName {
		case "go.mod":
			if m := goDirective.FindSubmatch(data); len(m) == 2 {
				note("target_go_requirement", string(m[1]))
			}
		case "package.json":
			var v struct {
				Engines struct {
					Node string `json:"node"`
				} `json:"engines"`
			}
			if json.Unmarshal(data, &v) == nil && requirement.MatchString(v.Engines.Node) {
				note("target_node_requirement", v.Engines.Node)
			}
		case "pyproject.toml":
			var v struct {
				Project struct {
					RequiresPython string `toml:"requires-python"`
				} `toml:"project"`
			}
			if toml.Unmarshal(bytes.TrimSpace(data), &v) == nil && requirement.MatchString(v.Project.RequiresPython) {
				note("target_python_requirement", v.Project.RequiresPython)
			}
		}
	}
	values := []string{}
	for k := range kinds {
		values = append(values, k)
	}
	sort.Strings(values)
	if len(values) > 0 {
		facts["target_manifest_set"] = strings.Join(values, "+")
	}
	multiple := false
	for key, choices := range declarations {
		if len(choices) == 1 {
			for value := range choices {
				facts[key] = value
			}
		} else {
			multiple = true
		}
	}
	facts["target_dependency_snapshot"] = domain.H(domain.Map{"scope_version": "registered-manifests/2", "coverage": coverage, "files": hashes})
	if multiple {
		return facts, coverage + "_MULTIPLE_REQUIREMENTS_UNKNOWN"
	}
	return facts, coverage
}

// CheckProjectFacts re-observes only registered, measured projects. It does not
// mutate pinned facts or invalidate old immutable query bundles.
func CheckProjectFacts(ctxFacts domain.Map, project Project, observe func(Project) (domain.Map, error)) error {
	now, err := observe(project)
	if err != nil {
		return err
	}
	current := domain.M(now["facts"])
	for _, key := range []string{"target_project", "target_revision", "target_branch", "target_worktree_state", "target_worktree_snapshot", "target_dependency_snapshot", "target_manifest_set", "target_go_requirement", "target_node_requirement", "target_python_requirement"} {
		old, was := ctxFacts[key]
		value, is := current[key]
		if was != is || (was && !codec.Equal(old, value)) {
			return errors.New("AEVORA_RUN_CONTEXT_CONFLICT")
		}
	}
	return nil
}
