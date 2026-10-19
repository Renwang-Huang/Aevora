# Aevora H2-G1 — Governance robustness acceptance

## Verdict and evidence scope

**G1 functional acceptance: PASS**, subject to the explicit limitations below.
This is a new H2 result on the current governance source, not an upgrade of H1.
No new model challenge was executed in G1. Graph fixtures exercise decision
contracts; they are not natural Agent engineering successes.

The new Full archive is
`aevora_validation/H2-20261011T082213Z-6bd12e96-82e1-4c87-b1df-67bc7fa74ae9/`.
Paths below are relative to that archive. `G1_GATE.json` is the admission record;
`release-g1-final/COMMIT_RECEIPT.json` records the actual independent release commit.
The root repository's historical HEAD does not contain these previously dirty
H1/H2 files; the release repository is explicitly a new source snapshot.

## Incremental implementation

The existing real FalkorDB repository, resolver, MCP service and trusted feedback
pipeline are retained. `aevora_core/docs/H2_GOVERNANCE.md` documents the contracts.

- Schema, query, WHEN and MCP interface versions advance to 1.1. The three
  public tools remain resolve_experience, build_evidence_bundle and record_decision.
  The bundle tool accepts optional same-Run query_id for frozen replay.
- Facts distinguish known true/false, UNKNOWN, NOT_OBSERVED and MISSING. Boolean
  and numeric comparisons are type strict; unknown does not become false.
- Rule publications append immutable revisions, factual scopes, validity and
  explicit SUPERSEDES links. Outcome observations do not publish new rules.
  Rival heads, cycles and missing declared relationships fail closed. Timestamps
  bound validity rather than deciding causal priority by recency.
- Withdrawal, expiration and scope restrictions preserve original evidence and
  target a typed `(label, id)`. A single uncertain/unrelated evidence path does
  not globally veto independent complete support.
- Support and counterexample relevance use factual material scope. Both paths
  remain visible; known unrelated failures do not become universal vetoes.
  Old capacity principles are distinguished from coverage of an entire new
  operation. New request-authority facts cannot be certified from old inventory
  successes.
- Actual immutable QuerySnapshots bind context, selected rule/revision, evidence,
  as-of time and engine versions. Decision and Feedback check the actual typed
  canonical CONSIDERED/DECIDED/RESPONDS_TO/AT_SNAPSHOT relationships and their
  payload/id/SHA. Participant decisions remain untrusted claims.
- Legacy checkpoint catalogs are verified before explicit 1.1 migration. Exact
  operational NODE constraints, bounded nonblocking credential reads and early
  candidate bounds are checked. Raw private Outcome fields are not public tool
  projection.
- `integrations/aevora.py` accepts six allowlisted public semantic facts from
  runtime.governance_context. Old manifests retain their exact projection; the
  Episode name does not choose a recommendation or supply repair evidence.

## Actual executions

Environment: independently acquired runtime, Python **3.12.14**, compiled official
SQLite **3.51.3**, authenticated isolated FalkorDB 4.20.4 / Redis 8.6.3, official
FalkorDB SDK 1.7.1, Redis SDK 8.1.0, MCP 1.26.0, pytest 9.1.1. Source and actual
package details are in `g1/full_project_v2/SOURCE_EPOCH.json` and the G0/runtime
receipts. H1 port 16379/volume are not used or modified.

The exact expanded argv, UTC start/end, exit, stdout/stderr hashes are in each
command.json. The environment paths refer to external owner-only password files,
not secret values. No password/API key is copied into the archive.

| New execution | Exit | Actual result |
|---|---:|---|
| g1-frozen-core | 0 | 388/388 core contracts: 286 predecessor contracts plus 102 new; 17 real GRAPH.COPY calls, no copy retry |
| g1-full-project-fixed-runtime-v2 | 0 | **1414/1414**, 173.137970 s outer duration; no failure/error/skip; one SDK settings warning |
| g1-history-identity-integrity | 0 | Original 1214 identities present/pass, 58 captured old test sources exact, 57 truth files exact, 101084 historical files exact |
| h2-g1-fixed-runtime-inherited-cli | 0 | All 15 existing lifecycle/classification checks completed, actual new Python/SQLite in reports |
| g1-current-schema-migration-receipt | 0 | Current idempotent real 1.1 migration; completion audit precedes after-state capture, old node/edge payloads preserved |

The complete regression was executed as:

```sh
env AEVORA_H2_RUNTIME="$H2_RUNTIME" \
  AEVORA_FALKORDB_PORT=17679 AEVORA_FALKORDB_GRAPH=aevora_h2_g0 \
  AEVORA_FALKORDB_PASSWORD_FILE="$H2_EXTERNAL_DB_PASSWORD_FILE" \
  scripts/aevora-h2-python -m scripts.aevora_h2_governance \
  --pause-auto-save tests "$H2_ARCHIVE/g1/full_project_v2" \
  -q tests aevora_core/tests
```

The variables denote the actual paths stored in the command receipt; use new
output directories to replay. The collector refuses overwriting evidence.
The actual JUnit SHA256 is
`b51b368e80bd4769d2d512d25cfaae7540b9042d53f6955609bf1bbe7e9de3de`.
All **282** source files before/after this acceptance match exactly.

The full regression collected **5374** official graph queries, **13856502** raw
bytes. The raw JSONL SHA256 is
`58cc197e27e8fa31cd93b366b7ad56bfd666281a44bbc41bb755027ae805b7fa`.
Actual parameters/results, errors, graph names and timestamps are retained in
`g1/full_project_v2/trusted_cypher_results.jsonl`; QuerySnapshot references include
source epoch, raw line number and line SHA. These raw private host results must
not be copied to a Participant.

The 28 requirement rows map actual test identities, Cypher and snapshots in
`g1/G1_EXECUTED_MATRIX.json`. The independent review and its closure are under
`security/g1-current-review/` and `security/g1-frozen-closure/`. They distinguish static findings from the new
actual graph-mutation rejection tests. The earlier review is not overwritten.
The matrix's REG01 retains its earlier pending state; this Gate's new full-suite
and identity receipts close it without rewriting that historical observation.

## Existing engineering truth remains independent

The 15 CLI checks have a separate result index
`g1/INHERITED_CLI_ACCEPTANCE.json` (SHA256
`e2b48b66b18705bfc6b51b1e414c9ab09b8bf03ab3bf8184ea86488ab6d8add1`).

| Scenario/control | New Run ID | Hidden result |
|---|---|---|
| SMOKE reference | f8502a5b-208f-4816-9a2b-a00b9fba8886 | PASS 8/8 |
| A reference | 7127aade-6f72-485e-a508-592a49ddd6f6 | PASS 14/14 |
| D-v01 reference | c7bd1379-6508-4d48-9573-9868e3fe1cea | PASS 28/28 |
| D-v01 distinct flock alternative | 67dcb913-fe24-4db0-972b-12e3bd259bd7 | PASS 28/28 |
| SMOKE/A/D-v01 buggy | See complete index | Real FAIL, respectively 8/8, 9/14 and 14/28 failures |
| Invalid submission | 034f7fc7-36d7-4c94-9ea5-3501ab844f5e | ERROR / exit 2 |
| Bounded evaluator interruption | 03be14bc-019e-48ad-9b93-8262ce8e1598 | TIMEOUT / exit 3 |
| B and C | See complete index | NOT_IMPLEMENTED / exit 4 |

Wrapper exit 0 means the classification checks passed. It does not turn an
expected buggy FAIL into a successful submission. These manual evaluations
do not demonstrate new Codex, experience adoption or causal benefit.

## Preserved failures and corrections

`g1/G1_EXECUTION_LEDGER.json` indexes all governance iterations. Root command
receipts additionally retain the failed module entry and its corrected replay.

1. First 43 new contracts: 18 PASS/25 FAIL, real FalkorDB projection/ORDER BY
   behavior. The implementation was corrected; assertions were retained.
2. Expanded contracts: 76 PASS/1 FAIL. A supposedly active fixture was future
   dated relative to the real MCP clock. Its effective time was explicitly
   corrected; the epoch assertion was not relaxed.
3. Two full core attempts contained actual GRAPH.COPY fork refusals. Automatic
   `save=60 1` was observed afterwards; the failure-instant competing fork was
   not captured. The causal explanation remains **UNVERIFIED**.
4. First copy observer used the wrong SDK info entry: 365 PASS/17 ERROR. The
   new collector was corrected to use the real SDK connection; original JUnit
   and output remain intact. This was collector failure, not a DB verdict.
5. First root module invocation failed in 0.305495 s with ModuleNotFoundError
   for the newly added helper. Direct/module import compatibility was repaired
   before the fresh full_project_v2 execution; the first directory remains.
6. The first migration receipt sampled after-state before completion AuditEvent.
   Its limitation remains explicit. The new schema_migration_v2 receipt uses
   the corrected implementation; the old receipt is not relabeled.

No failed result was deleted, replaced with H1 credit or changed into PASS.

## Persistence maintenance and remaining limitations

Core copy tests run in an explicit **temporary H2-only maintenance window**:
record existing SAVE/persistence state, pause automatic scheduling, wait boundedly
for an existing fork, execute unchanged tests, perform actual SAVE, restore and
verify `save=60 1` in finally. The final receipt records true explicit SAVE and
configuration restoration. No GRAPH.COPY retry or test relaxation was added.
This is not a production persistence setting or proof of the original fork cause.

Query/evidence collection spans multiple actual graph queries, not an atomic
distributed snapshot. Publication completion audits fail closed but are not a
distributed transaction. A trusted graph administrator remains a trust root.
No automatic reinstatement, rival-head arbitration or causal trust score is
implemented. New feedback preserves UNKNOWN attribution and does not promote
PASS into support for an unverified new operation.

RDB checkpoint RPO, unresolved AOF replay, shared-kernel isolation PARTIAL and
the EOL base runtime limitations from G0 remain. The actual warning is
pydantic_settings IncompleteFieldDefinitionWarning for the official MCP
lifespan annotation; initialization/tool contracts passed, but the warning is
retained rather than suppressed. Host hashes are local consistency evidence,
not third-party attestation. Governance benefit is **UNVERIFIED**.

D-v02 remains unimplemented at this Gate. Its new 1.0.2 implementation contract
and historical 0.3.0 design are distinct. G2 coding starts after this acceptance;
no new Task success, cross-family coverage or H3 development is claimed here.
