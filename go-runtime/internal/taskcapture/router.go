package taskcapture

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"path/filepath"
	"strings"
)

// Router observes the official runtime's thread directory, not a caller's project label.
// Unknown or out-of-workspace threads remain uncaptured rather than inheriting a route.
type Router struct {
	Workspace, ProjectName, Task string
	threads                      map[string]bool
}

func NewRouter(workspace, project, task string) *Router {
	return &Router{workspace, project, task, map[string]bool{}}
}
func (r *Router) inside(path string) bool {
	if !filepath.IsAbs(path) {
		return false
	}
	real, e := filepath.EvalSymlinks(path)
	if e != nil {
		return false
	}
	rel, e := filepath.Rel(r.Workspace, real)
	return e == nil && (rel == "." || (rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator))))
}
func (r *Router) Observe(raw []byte) (domain.Map, error) {
	v, e := wire.Decode(raw, MaxInput)
	if e != nil {
		return nil, e
	}
	thread := domain.M(domain.M(v["result"])["thread"])
	if v["method"] == "thread/started" {
		thread = domain.M(domain.M(v["params"])["thread"])
	}
	if id := domain.S(thread["id"]); id != "" {
		if len(r.threads) < 64 {
			r.threads[id] = r.inside(domain.S(thread["cwd"]))
		}
	}
	if v["method"] != "item/completed" {
		return nil, nil
	}
	p := domain.M(v["params"])
	if !r.threads[domain.S(p["threadId"])] {
		return nil, nil
	}
	item := domain.M(p["item"])
	if cwd := domain.S(item["cwd"]); cwd != "" && !r.inside(cwd) {
		return nil, domain.ErrInvalid
	}
	return Project(raw, r.ProjectName, r.Task)
}
