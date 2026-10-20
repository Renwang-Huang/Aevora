# Repository layout

Aevora is one engineering project. Its public interface consists of Core, scoped MCP tools and the read-only Console, backed by FalkorDB. Trusted Host verification governs publication and experience evolution. The optional OrderFlow Benchmark provides the task environment and independent evaluation used to develop and inspect those mechanisms.

| Path | Responsibility |
|---|---|
| `aevora_core/` | Core package, graph repository, arbitration, scoped MCP and Core tests |
| `console/` | Read-only HTTP API, browser UI, build and browser verification |
| `aevora_maintainer/` | Trusted Host source verification, review, publication and revocation |
| `integrations/` | Agent adapters, model/gateway brokers and controlled runtime integration |
| `deploy/` | Local product demo container and Compose configuration |
| `examples/observatory/` | Optional pinned replay, verifier, context and deployment example |
| `app/` | OrderFlow task application used by the optional Benchmark |
| `benchmark/` | Scenario preparation, Runner, CLI and public task tests |
| `evaluator/` | Independent evaluator, Oracle, disclosed tests and reference answers |
| `tests/` | Product, integration, security, contract and engineering tests |
| `scripts/`, `tools/` | Supported setup/reproduction entrypoints and retained validation tools |
| `docs/` | User guides, architecture, API contracts and developer instructions |
| `docs/history/` | Dated research, original phase contracts, development harness source and provenance |
| `evidence/` | Evidence-storage policy; generated run data remains outside source |

Run the product with [Quickstart](QUICKSTART.md), connect an Agent through [MCP setup](CODEX_MCP_SETUP.md), or reproduce the [Benchmark](BENCHMARK.md). Product Core/Console packages do not require Benchmark/evaluator installation.

## Historical names and compatibility

Research stages belong in the [history index](history/README.md). The old root `h4/` contained runnable replay/example resources; these now live in `examples/observatory/`. Historical engineering programs, original graph-contract development and evaluation disclosure records are grouped under history rather than presented as product modules.

Existing validation script/module names and episode identifiers are retained where external tooling or test identities use them. They describe source compatibility or evidence provenance. Graph v2 and MCP schema versions describe actual data/protocol contracts and remain explicit. The current product entrypoints are `scripts/aevora_public_demo.py`, the documented Core CLI/MCP tools, Console and the optional `orderflow` CLI.

[Product path relocations](history/PRODUCT_PATH_RELOCATIONS.csv) records old/new paths and both content hashes. Earlier root-cleanup maps and source manifests remain records of their original source epochs; the new map is a separate overlay. No historical result, development date, Oracle assertion or source pin is rewritten to make the current layout appear to have existed earlier.
