package host

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"testing"
)

func TestUnregisteredContextCannotInheritConfiguredTargetClaims(t *testing.T) {
	facts := map[string]any{"runtime_engine": "go_native", "target_project": "unrelated", "target_revision": "1234", "target_dependency_snapshot": "abc"}
	sources := map[string]any{"runtime_engine": "NATIVE_RUNTIME_OBSERVATION", "target_project": "PROTECTED_HOST_CONFIGURATION", "target_revision": "PROTECTED_HOST_CONFIGURATION", "target_dependency_snapshot": "PROTECTED_HOST_CONFIGURATION"}
	hash, err := codec.Digest(facts)
	if err != nil {
		t.Fatal(err)
	}
	value, err := runtimeOnlyObservation(map[string]any{"source": "TRUSTED_NATIVE_RUNTIME_OBSERVATION", "facts": facts, "fact_sources": sources, "facts_sha256": hash})
	if err != nil {
		t.Fatal(err)
	}
	clean := value["facts"].(map[string]any)
	cleanSources := value["fact_sources"].(map[string]any)
	if len(clean) != 1 || clean["runtime_engine"] != "go_native" || len(cleanSources) != 1 || value["target_observation"].(map[string]any)["status"] != "UNREGISTERED_WORKSPACE" {
		t.Fatal("unregistered task inherited target context", value)
	}
	if _, err = runtimeOnlyObservation(map[string]any{"source": "TRUSTED_NATIVE_RUNTIME_OBSERVATION", "facts": map[string]any{}, "fact_sources": map[string]any{}, "facts_sha256": "incorrect"}); err == nil {
		t.Fatal("unverified runtime observation accepted")
	}
}
