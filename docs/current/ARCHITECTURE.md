# Current architecture and ownership

The canonical layered graph is [Gen1.5 architecture](../../GEN1_5_TARGET_ARCHITECTURE.md).
Stable API paths/distribution names are preserved. [Dependency rules](../../GEN1_5_DEPENDENCY_RULES.md)
and the per-file migration map govern future changes.

Core alone owns WHEN/WHY and trusted lifecycle logic. Console/API/public integration
consumes bounded Core interfaces. GraphRepository reads real FalkorDB; Replay is
externally pinned public consistency evidence and cannot substitute for Live.
OrderFlow and its independent Oracle are included optional engineering source,
alongside the Trusted Host/native verifier and disclosed historical tests/answers.
Product-only Core/Console deployment remains independent of that optional package.
The current [full-project scope](../../FULL_PROJECT_SCOPE_AND_LICENSE.md) supersedes
the older Gen1.5 publication profile; its original design and migration records
remain historical references.

`aevora_maintainer.audit_capsule` is the included archive helper implementation;
`aevora.audit_capsule` is an optional legacy module-identity alias, not a product
runtime dependency. Explicit Outcome admission still checks registered authority
and sealed verifier-source pins. Source inclusion does not grant approval or
publication rights. Production keys, capability/registry data, original private
model sessions and some historical run evidence remain outside publication.

`tools/public_evidence` owns standalone stdlib verifier/disclosure bytes. The H4 and
Console copies are reproducibly generated, required for independent distributions,
and checked with `tools/sync_public_evidence.py --check`. They do not make governance
decisions. Deployment/Replay assets keep their stable h4 paths to avoid consumer churn.

Current commands are in DEVELOPMENT.md. Historical phase scripts remain reproducible;
some old entries write old archive/report paths and must not be used against sealed
history. Use fresh output directories through the current command entry.
