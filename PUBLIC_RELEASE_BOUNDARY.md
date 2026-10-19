# Full-project release boundary

The current publication scope is defined by
[FULL_PROJECT_SCOPE_AND_LICENSE.md](FULL_PROJECT_SCOPE_AND_LICENSE.md).
The earlier selected Core/Console/H4 allowlist was a **historical product-only
release profile**, not the scope of this full-project source candidate. Older
[product README](docs/PUBLIC_README.md), Gen1/H4 reports and archived taskbooks
retain their original phase descriptions and results.

## Current engineering source

The reviewed selection in `PUBLIC_SOURCE_FILES.txt`, used by
`tools/public_release.py`, includes Core, Console, Agent integrations, Trusted
Host/Q07 and native-source verification, OrderFlow `app/` and `benchmark/`, the
actual `evaluator/` and Oracle, formerly hidden tests/manifests/reference answers,
engineering tests, debug/experiment tools and labelled historical source.
See the [source map](docs/FULL_PUBLIC_SOURCE_MAP.md) and
[public historical evaluation disclosure](historical_public_evaluation/README.md).
Published answers no longer form a future blind evaluation.

Excluded publication inputs are actual credentials, signing private keys,
production Host registries/grants/capabilities, personal sensitive data, original
private model sessions, unsafe raw data and material without redistribution
rights. Some original historical run evidence remains unpublished. Public code
and summary hashes do not replace those original run records or certify a new
Agent execution or causal performance improvement.

## Product installation and trusted operation

Ordinary Core import/query/MCP, Console and the product demo image work without
installing the optional Benchmark/evaluator. Their deployment footprint is
smaller than the engineering repository. Trusted Host and Oracle source being
available does not add Host review/publication tools to the participant MCP API
or grant production authority to the synthetic demo registry.

`aevora_maintainer.audit_capsule` is included optional engineering source;
`aevora.audit_capsule` remains its legacy alias when the optional package is
installed. The former private `MAINTAINER_ONLY` packaging restriction is
historical. Optional Outcome admission still checks explicit authority and
matching sealed source; it does not infer trust from repository membership.

## Packaging and evidence safeguards

Release output must be fresh and external. Selection rejects traversal, links,
nonordinary files and credential paths. Generated source copies are checked by
`tools/sync_public_evidence.py --check`; Core alone decides WHEN/WHY. Replay
hashes establish consistency, not adoption or causal benefit.

Source/ZIP/wheel/sdist and reachable Git history require security/license review;
secret values and individual secret hashes must never enter artifacts. Preserve
original failures, the 51 legacy G1 SKIPs, B/C NOT_IMPLEMENTED, G24 NOT_RUN and
the unresolved FalkorDB SIGSEGV/139/AOF limits. This candidate remains local
pending owner publication approval; no GitHub push is part of the hotfix.
