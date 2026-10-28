package taskcapture

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/jsoncheck"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
)

type CheckBinding struct {
	Schema    string `json:"schema_version"`
	Backend   string `json:"backend_id"`
	Project   string `json:"project"`
	Workspace string `json:"workspace"`
	PlanFile  string `json:"plan_file"`
	PlanSHA   string `json:"plan_sha256"`
	TaskRef   string `json:"task_ref"`
	PlanValid bool   `json:"-"`
}

func InstallCheck(root, backend, project, workspace, path string) error {
	p, e := jsoncheck.Load(path)
	if e != nil {
		return e
	}
	if p.Project != project || p.TaskRef == "" {
		return domain.ErrInvalid
	}
	if e = jsoncheck.ValidateWorkspace(p, path, workspace); e != nil {
		return e
	}
	raw, e := platform.ReadPrivate(path, 65536)
	if e != nil {
		return e
	}
	dir := filepath.Join(root, "task-checks")
	if e = platform.PrivateDir(dir, true); e != nil {
		return e
	}
	entries, e := os.ReadDir(dir)
	if e != nil {
		return e
	}
	dest := filepath.Join(dir, project+".json")
	if _, e = os.Lstat(dest); os.IsNotExist(e) {
		if len(entries) >= 16 {
			return domain.ErrInvalid
		}
	} else if e != nil {
		return e
	} else {
		old, e := platform.ReadPrivate(dest, 4096)
		if e != nil {
			return e
		}
		var binding CheckBinding
		if json.Unmarshal(old, &binding) != nil || binding.Schema != "aevora.check-binding/1" || binding.Backend != backend || binding.Project != project {
			return domain.ErrConflict
		}
	}
	b := CheckBinding{Schema: "aevora.check-binding/1", Backend: backend, Project: project, Workspace: workspace, PlanFile: path, PlanSHA: domain.BytesSHA(raw), TaskRef: p.TaskRef}
	raw, e = json.Marshal(b)
	if e != nil {
		return e
	}
	return platform.Atomic(dest, raw)
}
func InstalledChecks(root, backend string) ([]CheckBinding, int) {
	dir := filepath.Join(root, "task-checks")
	entries, e := os.ReadDir(dir)
	if e != nil {
		return nil, 0
	}
	out := []CheckBinding{}
	invalid := 0
	for i, entry := range entries {
		if i >= 16 {
			invalid++
			break
		}
		raw, e := platform.ReadPrivate(filepath.Join(dir, entry.Name()), 4096)
		if e != nil {
			invalid++
			continue
		}
		v, e := wire.Decode(raw, 4096)
		if e != nil || len(v) != 7 {
			invalid++
			continue
		}
		var b CheckBinding
		if json.Unmarshal(raw, &b) != nil || b.Schema != "aevora.check-binding/1" || b.Backend != backend || entry.Name() != b.Project+".json" {
			invalid++
			continue
		}
		plan, e := platform.ReadPrivate(b.PlanFile, 65536)
		b.PlanValid = e == nil && domain.BytesSHA(plan) == b.PlanSHA
		if b.PlanValid {
			p, e := jsoncheck.Load(b.PlanFile)
			b.PlanValid = e == nil && p.Project == b.Project && p.TaskRef == b.TaskRef
		}
		if !b.PlanValid {
			invalid++
		}
		out = append(out, b)
	}
	return out, invalid
}

func DisableCheck(root, backend, project string) error {
	path := filepath.Join(root, "task-checks", project+".json")
	raw, e := platform.ReadPrivate(path, 4096)
	if e != nil {
		return e
	}
	var b CheckBinding
	if json.Unmarshal(raw, &b) != nil || b.Schema != "aevora.check-binding/1" || b.Project != project || b.Backend != backend {
		return domain.ErrInvalid
	}
	return os.Remove(path)
}
