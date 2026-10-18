# Aevora H2-G1 — factual governance and immutable query replay

## Scope and compatibility

H2 extends the existing FalkorDB repository, WHEN resolver, WHY bundle, MCP
service and trusted OrderFlow feedback bridge. It does not introduce a second
graph engine, an Agent orchestrator, a confidence score, an Episode identifier
policy table or causal attribution from test verdicts.

Current contracts are `aevora.graph/1.1`, `aevora.multihop/1.1`,
`aevora.when/1.1` and `aevora.mcp/1.1`. H1 node and edge payloads remain
immutable. The legacy `retrieval_snapshot_sha256` formula remains exactly:

```python
digest({"experience": bundle["experience"],
        "premise_paths": bundle["premise_paths"], "paths": bundle["paths"]})
```

New governance records are included in a separate
`governance_evidence_sha256`; Query, Decision and QuerySnapshot bookkeeping
cannot make that evidence hash increase or change by itself. These are byte
identifiers, not numerical reliability scores.

## Minimal graph additions

| Record or relationship | Meaning and authority |
|---|---|
| ExperienceRevision with `revision_kind=rule_publication` | Trusted append of an explicitly declared Rule, predecessors, source, factual scope and validity interval |
| ExperienceRevision with `revision_kind=outcome_observation` | Actual queried Rule epoch retained by feedback; never an applicability publication |
| SUPERSEDES | Explicit same-Experience predecessor relationship; creation time gives no priority |
| GovernanceEvent / GOVERNS | Trusted host withdrawal, expiration or scope restriction targeting Evidence or ExperienceRevision |
| QuerySnapshot / AT_SNAPSHOT | Immutable public projection of actual candidate, facts, as-of time and engine versions, with an actual Query association |

Public tools cannot publish Rule revisions, governance events or VerifiedOutcome.
Every publication or governance append has a deterministic completion AuditEvent,
written after its required relationships. Incomplete declarations, missing edges,
cycles, mismatching Rule declarations and rival applicable Rule heads produce
`VERIFY` with integrity diagnostics. Writes are individually append-only and
idempotent; they are not one multi-statement database transaction. A crash can
leave partial records and an identical trusted retry can complete them.

`append_rule_revision()` validates a bounded public Rule, at most 32 same-Experience
predecessors, public factual scope, explicit provenance and timezone-aware
validity. New Rule predicates use public semantic fact keys. Episode identifiers
cannot be new Rule conditions. Legacy imports keep their existing contract.

`append_governance_event()` accepts `withdraw`, `expire` and `restrict_scope`.
No automatic reinstatement, scoring or last-write-wins priority is implemented.
Withdrawal/expiry makes a target unavailable in its stated effective scope while
retaining original payloads and evidence. Restricting one Evidence filters that
Evidence's paths; another independent, applicable support chain remains usable.
A restriction on the selected Rule Revision constrains that Rule's use.
Restrictions attached to an inactive Revision do not add global material facts.

## Facts, conflicts and operation scope

| Observation | Handling |
|---|---|
| Known `true`, `false`, zero or scalar | Type-exact comparison; Python boolean/number equality cannot establish a premise |
| Missing key | `MISSING`, separately reported; never assumed false |
| Null, unknown or unavailable | `UNKNOWN`; required factual observation needs investigation |
| Explicit `not_observed` | `NOT_OBSERVED`, separately reported; not a known negative observation |
| Same applicable scope support and counterexample | Both original paths retained; `VERIFY`, no retrieval-order winner |
| Known different scope counterexample | Path remains visible but does not veto the current scope |
| Potentially relevant counterexample with unknown scope | `VERIFY`, with investigation context |
| Confirmed necessary premise violation | `ABSTAIN`, with the actual conflict or counterexample |

Only complete support paths with a PASS and matching recorded necessary
conditions can support a conditional principle. Required premises, deployment
scope and declared material facts are evaluated from the graph and current facts.
An optional unobserved predicate is not silently promoted into a required veto.

New operation semantics, authority, clock or supported-operation facts may be
material beyond an old inventory principle. The resolver returns
`principle_decision`, `principle_support_paths`, `current_operation_coverage`
and `missing_material_premises` alongside the overall decision. A local
inventory principle may remain conditionally supported while the new complete
request/lease operation is `VERIFY` because its material conditions were not
observed in historical evidence. This policy depends on facts and recorded
scope, not A/D task names. No recommendation is a guarantee of whole-task repair.

The six optional `runtime.governance_context` facts projected from a trusted
public manifest and later from a trusted report are `operation_semantics`,
`authority_model`, `authority_validation`, `clock_domain`,
`supported_operation_set` and `observed_failure_mode`. Absent extensions preserve
the H1 projection. Private keys and Episode identifiers are excluded.

## Query snapshots and evidence boundaries

The resolver persists the exact allowlisted candidate before adding its own
snapshot self-reference, together with current scalar facts, trusted host
as-of time and query/decision versions. The immutable snapshot ID is derived
from its canonical content SHA256. `build_evidence_bundle(experience_id,
query_id)` replays that Query's frozen public bundle; omitting `query_id` retains
the existing current-graph bundle behavior. Replay requires the actual Query,
same Run, candidate declaration, verified snapshot body and actual AT_SNAPSHOT
edge. It never substitutes a current bundle for a missing or corrupt snapshot.

The repository reads multiple statements. A snapshot is an immutable collection
of those actual observations, **not an atomic database transaction**. The
FalkorDB read-query `version` parameter invalidates cached schema mappings; it
is not a content snapshot. Trusted writers should be quiesced for consistency
boundaries such as checkpoint capture. Concurrent trusted updates remain an
explicit consistency limitation.

`scripts/aevora_h2_governance.py` records actual official SDK statements,
parameters, result rows, UTC intervals and raw line SHA256 under the trusted
Full archive. `QUERY_SNAPSHOT_REFERENCES.json` binds snapshot capture writes to
their preceding actual read line references and source epoch. These references
include preparatory reads and do not assert atomicity. Raw host rows may contain
private verification fields; they are never returned by MCP or copied to
Participant. Public snapshots and bundles contain the existing record allowlists.

## Trusted feedback remains qualified

The bridge still verifies the sealed OrderFlow outcome itself. Participant
claims cannot supply a verdict, trusted flag, governance event or causal benefit.
Feedback associates the actual QuerySnapshot Rule and Revision epoch rather
than whatever Rule happens to be current when ingestion occurs. Missing or
corrupt AT_SNAPSHOT associations fail closed. A legacy Query without a snapshot
keeps its legacy initial-Rule association and is explicitly not replayable.

PASS and FAIL are preserved as `OBSERVED_OUTCOME` when strategy adoption and
causal influence are unproved. Attribution remains `UNKNOWN`, adoption and
strategy association remain `UNVERIFIED`. A feedback revision cannot supersede
an applicability Rule merely because its outcome is newer.

## Schema and checkpoint migration

`schema_catalog()` has exact separate catalogs for H1 1.0 and H2 1.1. H1 has 15
labels and 30 exact NODE constraints; H2 adds two labels and has 34 exact NODE
constraints. Entity type, label, property set, constraint kind, duplicate absence
and OPERATIONAL status must all match. The same count of RELATIONSHIP constraints
cannot impersonate a NODE schema. Credential inputs are owner-only single-link
ordinary files, opened with NOFOLLOW/NONBLOCK and bounded reads plus post-read
identity checks; no value or secret hash is emitted.

A manifest-pinned old checkpoint is first validated with its old label,
relationship and constraint catalog and compared to the actual restored graph.
`verify_restored()` reports the original version and `NOT_AUTOMATIC` migration
status. Only then does an explicit trusted `migrate_governance()` append the new
constraints, Schema and completion AuditEvent. Old checkpoint bytes are not
rewritten or advertised as a new-version snapshot. After migration, a current
checkpoint must be captured separately. Existing G0 RDB cold-restore evidence
remains evidence for its frozen source, not a retrospective G1 recovery test.

## Reproduction and classifications

Set `AEVORA_H2_RUNTIME`, `AEVORA_FALKORDB_PORT=17679`,
`AEVORA_FALKORDB_GRAPH` and an external owner-only
`AEVORA_FALKORDB_PASSWORD_FILE`, then use a new, non-existing output directory:

```sh
scripts/aevora-h2-python scripts/aevora_h2_governance.py migrate <new-host-output>
scripts/aevora-h2-python scripts/aevora_h2_governance.py tests <new-host-output> \
  -q aevora_core/tests
scripts/aevora-h2-python scripts/aevora_h2_governance.py --pause-auto-save \
  tests <another-new-host-output> -q tests aevora_core/tests
scripts/aevora-h2-python scripts/aevora_h2_governance.py audit-history <new-host-output>
```

The test collector performs real official FalkorDB calls on UUID test graphs,
or isolated copies of verified history. Synthetic Rule/outcome fixtures prove
governance contracts; they are not new natural Agent engineering runs. Original
source hashes, failed attempts and corrected reruns are retained under the H2
Full archive. The parent Gate supplies the complete integrated history identity
and OrderFlow regression verdict.

The optional maintenance window is restricted to the dedicated H2 endpoint. It
records the original automatic SAVE configuration and persistence/stats, pauses
scheduling, drains an already active fork within five seconds before pytest,
runs unchanged assertions, then performs explicit RDB SAVE and restores/verifies
the original configuration in `finally`. The receipt is a temporary test
configuration, not a deployed persistence guarantee. Actual GRAPH.COPY calls
are observed with before/after persistence state; no copy is retried or faked.
Observer failures and actual Redis fork refusals remain distinct records.

## Primary references

The design follows explicit provenance, revision and invalidation concepts from
[W3C PROV-O](https://www.w3.org/TR/prov-o/) without claiming full ontology
conformance. Actual graph behavior uses the official
[FalkorDB SDK v1.7.1](https://github.com/FalkorDB/falkordb-py/blob/v1.7.1/falkordb/graph.py),
[constraint contract](https://docs.falkordb.com/commands/graph.constraint-create)
and [read-query contract](https://docs.falkordb.com/commands/graph.ro-query).
The [GRAPH.COPY implementation](https://github.com/FalkorDB/FalkorDB/blob/v4.18.0/src/commands/cmd_copy.c)
uses a Redis module fork; a server fork refusal is retained as an environment
error, never a successful clone or a reason to weaken tests.

## Remaining limitations

Trusted administrator integrity is assumed; local hashes are not third-party
attestation. Reads and append publication are not multi-statement transactions.
Governance supports withdrawal, expiry and restriction, not reinstatement or
conflict arbitration. Rule selection conservatively requires one effective Rule;
manual trusted resolution is required for competing heads. Current bounds are
256 candidates/revisions/governance events, 1,024 supersession edges and 256 KiB
per immutable record; oversized evidence fails rather than being silently
truncated. Synthetic contract results cannot establish natural Agent uptake,
LLM injection immunity, causal improvement or generalization beyond observed
contexts. Those require independently archived dynamic challenge evidence.
