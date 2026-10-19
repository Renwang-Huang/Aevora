# G0 dependency map

AST parse of306 Python modules /2689 import edges /0 parse errors, crossed with packaging, grep callers and current commands. Raw edges are in external `g0/PYTHON_DEPENDENCIES.json`; ownership of every selected source is in the migration CSV.

| Entry | Actual owner / call path | Trust / external dependency |
|---|---|---|
| `aevora` | Core cli→resolver/governance/lifecycle/graph repository | Public, real FalkorDB; host source/publication commands trusted only |
| scoped MCP | Core serve→authenticated broker→mcp_connect stdio SDK | Public restricted per-run tools; no graph admin/Oracle |
| Console | aevora_observatory.server→projection→Core reads | Public readonly; LIVE failure no Replay fallback |
| HeroVerifier | h4.verify_hero; exact Console vendor | Stdlib public Replay consistency, external contract SHA |
| `orderflow` | benchmark.cli→Runner/registry→evaluator/isolated worker | Private maintainer; hidden Oracle/Reference never public |
| Participant | participant_sandbox→Codex CLI→Gateway scoped host broker | Private host auth; native original runtime; no new challenge here |
| Audit Capsule | aevora.audit_capsule→benchmark.evidence_* + integrations.codex_trace | Improper top-level public/maintainer coupling; planned optional private alias |
| Outcome bridge | Core public types; deferred private submission/admission verifier | Explicit optional trusted host boundary; no ordinary runtime dependency |
| public build | scripts.aevora_h4_public allowlist, setuptools/Node/esbuild | Current tool to reuse under fresh external output; no sealed archive writes |
| H1–H4 phase tools | still imported by tests / provenance/replay collectors | Scope-bound adapters retained; not declared obsolete by name |

Byte-identical vendor tools have independent standalone deployment callers. License copies and frozen duplicate specs are necessary asset/history copies, not duplicate governance engines. No unknown file is authorized for deletion.
