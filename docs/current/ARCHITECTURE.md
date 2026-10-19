# Current architecture and ownership

The canonical layered graph is [Gen1.5 architecture](../../GEN1_5_TARGET_ARCHITECTURE.md).
Stable API paths/distribution names are preserved. [Dependency rules](../../GEN1_5_DEPENDENCY_RULES.md)
and the per-file migration map govern future changes.

Core alone owns WHEN/WHY and trusted lifecycle logic. Console/API/public integration
consumes bounded Core interfaces. GraphRepository reads real FalkorDB; Replay is
externally pinned public consistency evidence and cannot substitute for Live.
OrderFlow is a separate private Benchmark with its unchanged independent Oracle.

`aevora_maintainer.audit_capsule` is the single private archive helper implementation;
`aevora.audit_capsule` is an optional legacy module-identity alias, not a public runtime
dependency. The existing OrderFlow outcome bridge exposes public verifier types and
defers private submission/admission imports until explicit Host verification.

`tools/public_evidence` owns standalone stdlib verifier/disclosure bytes. The H4 and
Console copies are reproducibly generated, required for independent distributions,
and checked with `tools/sync_public_evidence.py --check`. They do not make governance
decisions. Deployment/Replay assets keep their stable h4 paths to avoid consumer churn.

Current commands are in DEVELOPMENT.md. Historical phase scripts remain reproducible;
some old entries write old archive/report paths and must not be used against sealed
history. Use fresh output directories through the current command entry.
