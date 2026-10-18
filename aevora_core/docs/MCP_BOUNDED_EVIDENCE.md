# Bounded public evidence transport (Local V5C.1)

The four public tools and original required arguments remain available. Optional
`cursor` on resolve and optional `cursor` / `view` on bundle are additive. The
resolver, full immutable query snapshots, graph records and Host authority are
unchanged. This is a public projection boundary, not a new decision engine.

`resolve_experience(task_context={})` returns sorted candidate summaries. Each
preserves the actual decision/reason, stable IDs, snapshot/governance hashes,
WHEN/WHY previews, per-category counts/hashes and a `detail_reference`.
`truncated=true` explicitly means this is a preview, including potentially
unfavorable omitted rows. Follow `next_cursor` while `has_more=true` using the
same context and SDK connection. All competitors remain accessible.

`build_evidence_bundle(experience_id, query_id)` retains the old complete shape
when it fits. `view="candidate"` with that query ID retrieves the full immutable
resolver candidate, including all counterexamples and full bundle. Oversized
public documents return lossless JSON Pointer entries (RFC6901): containers
precede children; whole values occupy their pointer; long strings have explicit
Unicode character offsets. Follow every page with the same IDs/view, reconstruct
the document and check `document_sha256` (the project's canonical JSON digest).
Never infer absence of counterevidence from a single page.

Budgets count official SDK1.26 text+structured JSONRPC encoding with worst-case
legal request ID and broker depth/node checks. Public pages are at most24576
compact bytes and196608 measured wire bytes; the existing262144 broker limit
is unchanged. Unicode is measured in UTF8 bytes. Context claims have an8192-byte
bound and retain the same eight-field strict schema and Host-only fact authority.

Continuations use connection-local HMAC-SHA256 capabilities, random document IDs,
immutable cached document hashes and bound operation/arguments. They expire after
900 seconds without extension and cannot cross SDK connections/runs. Cache is
finite (32 documents,16MiB serialized entries; individual detailed document8MiB).
Expiry/eviction requires restarting retrieval without a cursor. Each page rechecks
the original run/query/experience graph authorization; DB outage and removed
associations fail closed. Cache data never supplies applicability or verified
outcomes. A changed current graph does not rewrite the original immutable query.

Existing graph record/candidate/governance caps still apply before projection.
Exceeding a finite graph or document capacity is an explicit error, never an empty
or successfully truncated answer. This does not promise unbounded graph scale,
shared-kernel hostile isolation, crash/AOF recovery, or causal learning benefit.
