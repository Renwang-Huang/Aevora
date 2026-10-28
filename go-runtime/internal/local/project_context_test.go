package local

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestProjectObservationUsesRegisteredWorkspaceAndPreservesUnknowns(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	git := func(args ...string) string {
		t.Helper()
		argv := append([]string{"-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-C", root}, args...)
		c := exec.Command("git", argv...)
		c.Env = append(os.Environ(), "GIT_CONFIG_GLOBAL="+os.DevNull, "GIT_CONFIG_NOSYSTEM=1")
		out, err := c.CombinedOutput()
		if err != nil {
			t.Fatal(err, string(out))
		}
		return strings.TrimSpace(string(out))
	}
	git("init", "-q", "-b", "main")
	git("commit", "-q", "--allow-empty", "-m", "fixture")
	head := git("rev-parse", "HEAD")
	base := domain.Map{"source": "TRUSTED_NATIVE_RUNTIME_OBSERVATION", "facts": domain.Map{"runtime_engine": "go_native"}, "fact_sources": domain.Map{"runtime_engine": "NATIVE_RUNTIME_OBSERVATION"}, "facts_sha256": domain.H(domain.Map{"runtime_engine": "go_native"}), "limitations": []any{}}
	project := Project{Name: "fixture-project", Workspace: root}
	// Caller environment must not redirect the trusted probe to another repo.
	t.Setenv("GIT_DIR", filepath.Join(root, "absent"))
	first, err := ObserveProject(ctx, project, base)
	if err != nil {
		t.Fatal(err)
	}
	facts := domain.M(first["facts"])
	if facts["target_project"] != project.Name || facts["target_revision"] != head || facts["target_branch"] != "main" || first["facts_sha256"] != domain.H(facts) {
		t.Fatal(first)
	}
	raw, _ := codec.Canonical(first)
	if strings.Contains(string(raw), root) || strings.Contains(string(raw), "fixture@example") {
		t.Fatal("private workspace data leaked")
	}
	if err := os.Unsetenv("GIT_DIR"); err != nil {
		t.Fatal(err)
	}
	git("checkout", "-q", "-b", "changed-branch")
	second, err := ObserveProject(ctx, project, base)
	if err != nil || second["facts_sha256"] == first["facts_sha256"] {
		t.Fatal("target change invisible", second, err)
	}
	git("checkout", "-q", "--detach")
	detached, err := ObserveProject(ctx, project, base)
	if err != nil || domain.FactState(domain.M(detached["facts"]), "target_branch") == "KNOWN" {
		t.Fatal("invented detached branch", detached, err)
	}
	project.Workspace = t.TempDir()
	plain, err := ObserveProject(ctx, project, base)
	if err != nil || domain.FactState(domain.M(plain["facts"]), "target_revision") == "KNOWN" {
		t.Fatal("unversioned directory gained a revision", plain, err)
	}
	if _, err := ObserveProject(ctx, project, domain.Map{"facts": domain.Map{}}); err == nil {
		t.Fatal("untrusted base observation accepted")
	}
}
