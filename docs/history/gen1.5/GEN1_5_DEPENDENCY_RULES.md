# Dependency rules

- PUBLIC Core ordinary import/query/MCP/CLI must not import Benchmark/Evaluator/integrations. `aevora.audit_capsule` is explicitly optional/private; legacy alias raises a clear installation error in a Core-only environment.
- `orderflow_outcome_bridge` remains an optional trusted Host verifier: public types stay; deferred Benchmark parser/admission imports require the explicit maintainer install. No participant tool exposes this path.
- Console uses Core public read interfaces; the two generated evidence tools are stdlib-only disclosure/verifier copies, never WHEN/WHY engines.
- Maintainer depends on Core; Core installation does not require the maintainer distribution. Root build backend retains MAINTAINER_ONLY enforcement.
- Public release selects explicit roots/files. No app/benchmark/evaluator/integrations/root AGENTS/tests/archives/credentials/DB volume enter public source, wheels, sdists, image or static resources.
- Generated copies must byte-match canonical tools; generated frontend must match build manifest. Replay contract pins and historical IDs remain unchanged.
- Full/Lite/history are external and immutable. New validation outputs use a fresh external directory; no phase script may write a sealed archive during consolidation.
- All inherited 1802 test identities and original source assertions remain; no skip/removal/relaxation. New migration tests are additive.
