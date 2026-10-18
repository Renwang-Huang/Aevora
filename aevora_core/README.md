# Gen2 release candidate — current product path

Use the [public release README](../README.md), [Graph v2 model](../docs/GRAPH_MODEL.md),
[actual Cypher](../docs/CORE_CYPHER.md) and [synthetic Decision Journey](../docs/DEMO_WALKTHROUGH.md).
The current public path includes complete scoped Graph v2 WHEN/WHY and the four
MCP tools. Production TrustedHost/Q07 authentication stays a separate trusted
integration; the demo's synthetic publisher is never production admission.
The following reference also documents preserved legacy/H4 compatibility.

# Aevora Experience Accountability Core

Aevora is an independent MCP-first experience governance product. FalkorDB is
its actual graph authority. OrderFlow Incident Lab remains a separate trusted
Benchmark and is not required to install, query or serve this package.

Aevora explains when an engineering experience applies, why its evidence is
relevant, and what a trusted outcome can support. A query is not proof of
adoption. External project self-tests and Agent claims remain unverified.

## Standalone runtime

Python >=3.12,<3.13; pinned dependencies FalkorDB SDK1.7.1, Redis8.1.0 and
MCP1.26.0. No automatic substitution of upstream SDKv2.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install ./aevora_core
```

Follow [the product Quickstart](../docs/QUICKSTART.md) for an independently
owned, authenticated loopback FalkorDB deployment and an ordinary project MCP
connection. A fresh graph is empty; no static success or historical database
is silently loaded. The installed package works without benchmark/integrations.

## Interfaces and authority

- `GraphRepository`: real official SDK, canonical records, bounded Cypher and
  actual graph constraints. No JSON database fallback.
- `ExperienceResolver` / evidence bundle: authoritative WHEN/WHY, support,
  counterexamples, scoped/unknown premises and immutable QuerySnapshots.
- Candidate lifecycle: untrusted proposal, evidence-pending, independently
  verified Host admission, publication, rejection and withdrawal.
- Official MCP: resolve_experience, build_evidence_bundle, record_decision;
  opt-in typed propose_experience. No admin/Cypher/Outcome tool.
- `aevora serve`: trusted Host owns DB credentials and a revocable scoped
  channel. `aevora.mcp_connect` is the stdlib ordinary consumer. The benchmark
  participant's fixed-path proxy and physical boundaries remain unchanged.
- Host CLI init/health/query/inspect/review/source-orderflow is administrative;
  never install its DB credentials in an untrusted Agent environment. The
  source-orderflow bridge is optional trusted maintainer integration, not a
  public project self-test shortcut to VerifiedOutcome.

Default grant lifetime follows its Owner. Optional explicit capability TTL
is available for local demonstrations; it is not a fixed runtime deadline for
healthy completion-aware Codex. Source pins, raw events and actual Outcome
receipts remain separate from natural-language Agent statements.

## Hero evidence and limits

The H4 three-case Hero uses actual H3 natural publication, factual conflict and
controlled graph intervention. The public replay has a separately pinned
independent standard-library verifier. Its presentation sequence is not one
invented cross-Rule causal history. Governance and Raw Memory's ordinary H3
pilot both passed seven public tests and remain EXTERNAL_UNVERIFIED.

H1-H3 historical evidence remains unchanged. H3 overall CONDITIONAL PASS and
its limitations persist: native cross-process UDS EPERM, AOF reload139, RDB
last-completed-SAVE recovery boundary, shared-kernel/EOL, unknown causal benefit
and adoption. Multi-step graph operations are not globally transactional;
local hashes are not external attestation. Ordinary same-UID developer mode
is not a hostile execution sandbox.

H4 was the preceding public product iteration. See the separately delivered
product docs for actual Gate/source epochs and observations; configuration
files alone are not evidence of live model execution or task success.

## Core reference

[Architecture](docs/ARCHITECTURE.md), [schema](docs/GRAPH_SCHEMA.md),
[queries](docs/QUERY_COOKBOOK.md), [WHEN/WHY](docs/WHEN_WHY_FEEDBACK.md),
[trust boundary](docs/TRUST_BOUNDARY.md), [lifecycle](docs/H3_LIFECYCLE.md).
