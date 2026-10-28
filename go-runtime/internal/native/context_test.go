package native

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"runtime"
	"testing"
)

func TestRuntimeFactsAreObservedAndConflictsFailClosed(t *testing.T) {
	observation, err := observedContext(domain.Map{"worker_count": 2})
	if err != nil {
		t.Fatal(err)
	}
	facts := domain.M(observation["facts"])
	if facts["runtime_os"] != runtime.GOOS || facts["runtime_arch"] != runtime.GOARCH || facts["storage_backend"] != "sqlite" || facts["worker_count"] != 2 {
		t.Fatal(observation)
	}
	if observation["facts_sha256"] != domain.H(facts) {
		t.Fatal("observation unpinned")
	}
	if _, err = observedContext(domain.Map{"runtime_engine": "python_reference"}); err == nil {
		t.Fatal("conflicting configured runtime accepted")
	}
	if domain.NormalizeContext(domain.Map{"runtime_engine": false}, true) == nil {
		t.Fatal("typed fact accepted boolean")
	}
	if domain.ValidateScope(domain.Map{"storage_backend": []any{"imaginary"}}) == nil {
		t.Fatal("unregistered fact value accepted")
	}
}
