# Public release boundary

Authoritative builder: `tools/public_release.py`. Selection is an explicit
allowlist inherited from the validated H4 product, with the canonical stdlib
evidence source and generation tool added. Release output is fresh and external.
The builder never traverses root maintainer archives, linked source, host auth
or private truth; it does not use a blanket Git add or old sealed release output.

| Included | Excluded |
|---|---|
| Core source/metadata, Console runtime/static/web/locked build inputs | app/benchmark/evaluator/integrations/aevora_maintainer |
| Public Core docs/ordinary Receipt example | Hidden suites/Oracle/Reference/Private Manifest/labels |
| Public docs, bootstrap, H4 Hero/Replay/context/deployment | Root maintainer AGENTS/tests/reports/task books |
| Canonical public evidence source + exact generation tool | Full/Lite/Raw model events/other Runs/DB backups/volumes |
| MIT/third-party notices | Gateway/DB credentials, scoped grants, personal auth/config |

Normal Core import/query/MCP and Console work in clean environments with neither
Benchmark nor Evaluator installed. Optional `aevora.audit_capsule` is a clear
legacy alias requiring the separately authorized private MAINTAINER_ONLY build;
its implementation is absent from all public artifacts. Existing trusted Outcome
bridge private dependencies are deferred to explicit Host verification, never
ordinary query or a participant MCP tool.

Supply-chain copies are required standalone assets, not competing engines.
`tools/sync_public_evidence.py --check` validates both consumer bytes and recorded
source ownership. Core alone decides WHEN/WHY. Replay contract digest remains
unchanged and means consistency, not external attestation/adoption/causal benefit.

Acceptance inspects actual source/ZIP/wheel/sdist members, public Docker filesystem
layers and browser payloads; exact private file bytes and known secrets/individual
hashes are scanned only in trusted memory. Archive extraction is not used to
execute unknown paths. Clean installed SDK/empty graph/source path and module
origin checks are distinct from developer test PASS. Local distribution only;
no Git push, public hosting or competition eligibility certification occurs.
