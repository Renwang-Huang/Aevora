# Governance and authorization evidence

Acceptance:58/58 actual new tests, real owned FalkorDB; raw per-process streams, final graph snapshots and persistent private pins are in `06_regression/acceptance-host-58/`.

- Actual new Host source/outcome publication gives APPLY. Actual negative engineering outcome creates COUNTEREXAMPLE, never SUPPORT, and gives ABSTAIN.
- Prepared withdrawal remains invisible; after atomic activation, old reference bytes remain equal and current read gives ABSTAIN.
- Scope restriction removes optimistic APPLY. Explicit revision supersession preserves old records and updates both Candidate heads atomically. Terminal candidates cannot resurrect.
- One authority withdrawal updates all affected complete manifests/catalogues, immutable observations and authz/semantic epochs in one query. New scoped partition discovery handles a2048-experience tenant without passing the whole tenant through one256-candidate query. Unknown all-partition recall still correctly returns CAPACITY_EXCEEDED.
- Unused verifier can be revoked before first publication. Current revocation between Host check and final query blocks activation. Old SDK grants/cached responses are denied; a fresh grant reads governed data.
- Real official SDK output computed before withdrawal is retained in private JSONRPC evidence; withdrawal before the Broker final check prevents delivery. Received EOF is distinct from SDK isError. Unauthorized Host method names close before SDK dispatch and have no graph effect.
- Source body/review pins, fake Agent/Run/tree/patch, wrong/absent verifier, ordinary7-self-test claim, tenant/profile/generation/expiry, extra/missing chunks, scope widening and final native label/type/endpoint tampering are rejected.

Inherited108 graph tests retain A single-process RLock→D cross-process negative transfer, unknown-context VERIFY, scoped legal support APPLY, same-domain authoritative conflict VERIFY, disjoint-domain compatibility, full Counter and graph intervention checks. They remain HOST_CONTROLLED_SYNTHETIC_FIXTURE, not new Agent outcomes.

Authorization boundary: physical Host selector + live capability + Q08 epoch/session + Broker pre-send recheck/local lock. External DB-to-network send is NOT a distributed atomic transaction; already delivered bytes cannot be revoked. Normal delivery events contain the measured check+send interval (an upper bound, not a precise isolated post-check window). No stronger hostile-kernel/UID or remote attestation claim.
