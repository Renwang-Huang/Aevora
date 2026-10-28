package native

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/buildinfo"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"runtime"
)

// Collected in the trusted native runtime, never from model arguments or a
// repository script. These facts describe this runtime, not arbitrary targets.
func observedContext(configured domain.Map) (domain.Map, error) {
	facts := domain.Clone(configured)
	sources := domain.Map{}
	for key := range configured {
		sources[key] = "PROTECTED_HOST_CONFIGURATION"
	}
	measured := domain.Map{"runtime_os": runtime.GOOS, "runtime_arch": runtime.GOARCH,
		"runtime_engine": "go_native", "storage_backend": "sqlite", "console_access": "loopback_read_only", "runtime_version": buildinfo.Version, "runtime_revision": buildinfo.Revision}
	for key, value := range measured {
		if previous, ok := facts[key]; ok && domain.FactState(facts, key) == "KNOWN" && !codec.Equal(previous, value) {
			return nil, domain.ErrConflict
		}
		facts[key] = value
		sources[key] = "NATIVE_RUNTIME_OBSERVATION"
	}
	if err := domain.NormalizeContext(facts, true); err != nil {
		return nil, err
	}
	return domain.Map{"schema_version": "aevora.context-observation/1", "fact_catalog_version": "aevora.fact-catalog/1",
		"source": "TRUSTED_NATIVE_RUNTIME_OBSERVATION", "observed_at": domain.Now(), "facts": facts, "fact_sources": sources,
		"facts_sha256": domain.H(facts), "limitations": []any{"Runtime facts describe the current local Host. They do not establish target platforms, test outcomes, adoption or causal benefit."}}, nil
}
