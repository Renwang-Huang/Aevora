package buildinfo

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"runtime"
	"runtime/debug"
	"sort"
)

var Version = "0.6.0-dev"
var Revision = "unknown"

func Current() map[string]any {
	dependencies := []map[string]string{}
	settings := map[string]string{}
	if info, ok := debug.ReadBuildInfo(); ok {
		for _, m := range info.Deps {
			dependencies = append(dependencies, map[string]string{"module": m.Path, "version": m.Version, "sum": m.Sum})
		}
		for _, s := range info.Settings {
			if s.Key == "CGO_ENABLED" || s.Key == "GOOS" || s.Key == "GOARCH" {
				settings[s.Key] = s.Value
			}
		}
	}
	sort.Slice(dependencies, func(i, j int) bool { return dependencies[i]["module"] < dependencies[j]["module"] })
	contractsHash := map[string]string{}
	for _, name := range []string{"tools.json", "reference.json", "facts.json"} {
		raw, e := contracts.Files.ReadFile(name)
		if e == nil {
			h := sha256.Sum256(raw)
			contractsHash[name] = hex.EncodeToString(h[:])
		}
	}
	return map[string]any{"product": "Aevora", "version": Version, "revision": Revision, "go_version": runtime.Version(), "os": runtime.GOOS, "arch": runtime.GOARCH, "settings": settings, "dependencies": dependencies, "contracts_sha256": contractsHash, "storage_schema": storage.PhysicalVersion, "capture_record_reader": 2, "task_memory_reader": 1, "native_platform_validation": "REQUIRES_SEPARATE_ACCEPTANCE_EVIDENCE"}
}
