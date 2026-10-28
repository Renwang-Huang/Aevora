package local

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var revision = regexp.MustCompile(`^[0-9a-f]{40}([0-9a-f]{24})?$`)

// ObserveProject is called only by trusted local/Host enrollment, never by MCP
// arguments. It executes no repository scripts, filters, pagers or hooks and
// does not copy paths, remotes, file contents or credentials into public facts.
func ObserveProject(ctx context.Context, p Project, observation domain.Map) (domain.Map, error) {
	if !Name.MatchString(p.Name) || observation["source"] != "TRUSTED_NATIVE_RUNTIME_OBSERVATION" || observation["facts_sha256"] != domain.H(observation["facts"]) {
		return nil, ErrInvalid
	}
	real, err := filepath.EvalSymlinks(p.Workspace)
	if err != nil || real != p.Workspace || !filepath.IsAbs(real) {
		return nil, ErrInvalid
	}
	facts, sources := domain.Clone(domain.M(observation["facts"])), domain.Clone(domain.M(observation["fact_sources"]))
	measured := domain.Map{"target_project": p.Name}
	status := "GIT_UNAVAILABLE_OR_UNVERSIONED"
	readGit := func(args ...string) (string, error) {
		bounded, cancel := context.WithTimeout(ctx, 2*time.Second)
		defer cancel()
		argv := append([]string{"--no-pager", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.DevNull, "-c", "core.untrackedCache=false", "-C", p.Workspace}, args...)
		command := exec.CommandContext(bounded, "git", argv...)
		// GIT_DIR/WORK_TREE and injected config must not select a different repo.
		for _, env := range os.Environ() {
			if !strings.HasPrefix(strings.ToUpper(env), "GIT_") {
				command.Env = append(command.Env, env)
			}
		}
		command.Env = append(command.Env, "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL="+os.DevNull, "GIT_TERMINAL_PROMPT=0", "GIT_OPTIONAL_LOCKS=0")
		pipe, err := command.StdoutPipe()
		if err != nil {
			return "", err
		}
		if err = command.Start(); err != nil {
			return "", err
		}
		data, readErr := io.ReadAll(io.LimitReader(pipe, 262145))
		if readErr != nil || len(data) > 262144 {
			cancel()
		}
		err = command.Wait()
		if readErr != nil || len(data) > 262144 {
			return "", ErrInvalid
		}
		return string(data), err
	}
	top, topErr := readGit("rev-parse", "--show-toplevel")
	if head, err := readGit("rev-parse", "--verify", "HEAD"); topErr == nil && strings.TrimSpace(top) == p.Workspace && err == nil && revision.MatchString(strings.TrimSpace(head)) {
		head = strings.TrimSpace(head)
		measured["target_revision"] = head
		status = "GIT_HEAD_OBSERVED"
		if branch, err := readGit("symbolic-ref", "--quiet", "--short", "HEAD"); err == nil && domain.NormalizeContext(domain.Map{"target_branch": strings.TrimSpace(branch)}, true) == nil {
			measured["target_branch"] = strings.TrimSpace(branch)
		} else {
			status = "GIT_HEAD_OBSERVED_BRANCH_UNKNOWN"
		}
		if work, err := observeWorktree(p.Workspace, readGit); err == nil {
			for k, v := range work {
				measured[k] = v
			}
		}
		// Do not combine an old HEAD with a new branch/worktree snapshot.
		if final, err := readGit("rev-parse", "--verify", "HEAD"); err != nil || strings.TrimSpace(final) != head {
			return nil, errors.New("AEVORA_TARGET_CONTEXT_CHANGED_DURING_OBSERVATION")
		}
		finalBranch, branchErr := readGit("symbolic-ref", "--quiet", "--short", "HEAD")
		if branchErr != nil || domain.NormalizeContext(domain.Map{"target_branch": strings.TrimSpace(finalBranch)}, true) != nil {
			finalBranch = ""
		}
		if strings.TrimSpace(finalBranch) != domain.S(measured["target_branch"]) {
			return nil, errors.New("AEVORA_TARGET_CONTEXT_CHANGED_DURING_OBSERVATION")
		}
	}
	manifest, manifestStatus := observeManifests(p.Workspace)
	for key, value := range manifest {
		measured[key] = value
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	for key, value := range measured {
		if domain.FactState(facts, key) == "KNOWN" && !codec.Equal(facts[key], value) {
			return nil, errors.New("AEVORA_TARGET_CONTEXT_CONFLICT")
		}
		facts[key] = value
		sources[key] = "TRUSTED_LOCAL_PROJECT_OBSERVATION"
	}
	// A failed Git probe must not preserve stale configured or previously
	// measured target revisions as if they were observed this time.
	for _, key := range []string{"target_revision", "target_branch", "target_worktree_state", "target_worktree_snapshot", "target_manifest_set", "target_dependency_snapshot", "target_go_requirement", "target_node_requirement", "target_python_requirement"} {
		if _, ok := measured[key]; !ok {
			delete(facts, key)
			delete(sources, key)
		}
	}
	if err := domain.NormalizeContext(facts, true); err != nil {
		return nil, err
	}
	out := domain.Clone(observation)
	out["facts"], out["fact_sources"], out["facts_sha256"] = facts, sources, domain.H(facts)
	worktreeStatus := "UNAVAILABLE_OR_LIMITED"
	if measured["target_worktree_snapshot"] != nil {
		worktreeStatus = "GIT_STATUS_AND_CHANGED_FILE_METADATA_OBSERVED"
	}
	out["target_observation"] = domain.Map{"status": status, "observed_at": domain.Now(), "scope": "REGISTERED_WORKSPACE_AT_OBSERVATION", "working_tree_content": "GIT_STATUS_AND_FILE_METADATA_NOT_CONTENT_ATTESTATION", "worktree_status": worktreeStatus, "manifest_status": manifestStatus, "manifest_requirement_policy": "SINGLE_DECLARATION_VALUE_ACROSS_OBSERVED_MODULES_OR_UNKNOWN", "model_configuration": "NOT_MEASURED"}
	out["limitations"] = append(append([]any{}, domain.A(observation["limitations"])...), "target_* is a bounded local observation. Worktree fingerprint covers Git status and changed-file metadata, not every file's contents; manifest requirements are declarations, not installed versions. Model overrides, tests, adoption and causal benefit remain unmeasured. Changed target facts require a new task.")
	return out, nil
}
