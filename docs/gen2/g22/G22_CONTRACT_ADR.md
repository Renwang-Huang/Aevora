# G22 contract amendments and trust boundary

This taskbook supersedes historical stop rules. The G20/G21 frozen design assets
are retained byte-for-byte, including their NOT_IMPLEMENTED handoff statuses.

1. Trusted Host facade and final-query compiler live in `aevora_maintainer`, excluded
   from the public release allowlist and Core/Console wheels. No fifth MCP tool.
2. Immutable OS-owned single-link0700/0600 pins now authenticate Candidate bodies,
   Source/Outcome checks, Review and Prepared roots as well as the existing four
   Reader pin categories. Pins are prepared durably before graph visibility;
   they never confer visibility without COMMITS, complete catalogues and epoch.
   An incomplete/unpinned orphan stays unavailable; resume with a fresh request
   after re-verification, never automatically bless a surviving DB row.
3. Host bootstrap may select a lookup-only private `registry.pin_root` instead of
   the unchanged legacy four dictionaries. This is Host config, never a tool arg.
   Registry reads do not cache authorization, revocation or negative evidence.
4. Candidate enters PUBLISHING by its prepublication CAS. Final activation adds
   immutable Published Event, unique receipt, all semantic/activation links,
   LifecycleHead and canonical TenantState in one GRAPH.QUERY. Concurrent epochs
   serialize all visibility changes; unrelated conflicts require explicit retry.
5. Governance observations can append an event/head sequence without changing
   its state. They are explicitly not state transitions. Terminal states never
   become active again; new proposals/revisions require new IDs. Revision
   supersession updates the old and new Candidate heads in the same final query.
6. Authority withdrawal is a bounded tenant operation: validate every complete
   affected witness, append scoped Evidence withdrawals and cumulative manifests,
   refresh every affected partition, append unchanged-state Candidate observations,
   and advance semantic/authz epochs in one final query. Historical Authorities
   and Outcomes remain immutable; new publication from a revoked verifier fails.
   Old grants/cursors fail; a newly issued grant reads the governed graph.
7. ID projections candidate_id/event_id/sequence implement the previously required
   Q07 native head fence. They are additive; first-generation Schema/4 tools stay
   unchanged. G21 never implemented active Host LifecycleHead publication.
8. Positive fact/scope validation proofs are keyed by complete immutable JSON,
   bounded2048 entries. Mutable values are never returned from the cache; registry,
   scope, epoch, current Authority and authorization are checked every time.
9. Q11 splits outgoing and incoming traversal and explicitly indexes the reverse
   target with WITH. Incoming external governance is still inspected. Limits,
   Counter sets, full Q04 paths and complete Catalogue checks are unchanged.
10. Source labels distinguish HOST_SEEDED/AGENT_PROPOSED and raw synthetic graph
    capacity fixtures. Native proposal actor thread is UNAVAILABLE when exact
    actor identity cannot be joined. No new model challenge or causal claim.

Single-query atomicity was tested on pinned4.20.4; it does not extend over staging,
Host filesystem persistence, DB/network delivery, or unsaved power loss. Broker
pre-send Q08 and local lock remain; external DB-to-send race and delivered bytes
are explicitly outside a distributed atomic authorization guarantee. RDB lastSAVE
RPO, AOF139 and shared-kernel PARTIAL remain known limitations.
