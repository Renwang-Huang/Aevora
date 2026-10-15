# Aevora

Context-aware engineering experience for coding agents, backed by FalkorDB.

## Repository stage

This repository currently contains documentation and an architecture outline.
Executable product code will be introduced separately in small, reviewed steps.
Existing local development is preserved independently; these commit dates record
publication of this documentation, not the original implementation dates.

## Design focus

- Decide WHEN an experience applies and inspect WHY the graph supports it.
- Keep Agent observations separate from independently verified outcomes.
- Connect coding agents through a scoped MCP interface.
- Make evidence and governance visible through a read-only console.

See [the architecture outline](docs/ARCHITECTURE.md) for module boundaries.
FalkorDB is the graph database. OrderFlow Incident Lab remains an independent
Benchmark and is not a runtime dependency of the product.
