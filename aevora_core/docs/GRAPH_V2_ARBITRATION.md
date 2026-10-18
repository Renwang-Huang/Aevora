# Graph-native arbitration — explicit rc2 read profile

G21 adds an opt-in `aevora.mcp/2.0.0-rc2` profile and a separate
`aevora.graph/2.0.0-rc2` physical graph. Legacy1.2 tools and old graphs retain
existing behaviour. Core remains installable without the independent Benchmark.

A trusted Host constructs `GraphRepository.v2(TenantBinding(...), TrustRegistry(...))`.
The binding selects an owned `aevora_v2_...` graph; tools cannot select tenants,
physical graphs, principals, authorities or outcomes. The registry must pin
validated publication manifests, registered independent verifier records,
exact outcome digests and known phase-fact receipts. Hashes are local integrity
pins, not signatures or independent source verification by themselves.

The reader uses fixed official-SDK Cypher templates, native indexes and mandatory/
unique constraints, full payload/endpoint checks, a complete published closure,
and start/end semantic/authz epoch checks. Facts distinguish task, artifact_before,
artifact_after and evaluation. Recommendations are APPLY/VERIFY/ABSTAIN; unknown
premises, conflicts, scope, governance and actual counterexamples remain visible.
Recommendation is not proof that the current patch passed or that an Agent adopted
an experience. Missing negative edges and over-budget data explicitly fail.

Host-only `MCPBroker(..., protocol_profile="aevora.mcp/2.0.0-rc2",
v2_config_path=..., enable_proposals=True)` selects the new profile. Its private
configuration contains `binding`, `registry`, `facts` and `grant`; the DB password
stays in a separate private Host file. The grant pins tenant/run/session/generation,
profile, UTC expiry and authz epoch. The existing proxy transports the same four
tool names. `read_scope` is non-sensitive response metadata, not a credential.

Large responses use the existing lossless JSON Pointer pages and connection-local
HMAC cursors. Fetch every page and verify the complete document SHA. Every page
rechecks actual graph integrity, permission, epoch and time-effective lifecycle.
The original262144-byte broker limit is unchanged. Published records and snapshots
use at most128 chunks of64KiB UTF8, at most8MiB/document. Relevant candidate count
above256 and evidence paths above512 fail explicitly; unrelated partitions do
not consume the candidate budget. No partial APPLY or silent fallback.

The local broker serializes owner revocation and output, with a successful-delivery
SHA/byte receipt. Database check and network send are not a distributed atomic
transaction; an external DB-to-send interval remains. Already delivered bytes
cannot be recalled. Source/Host review and full publication CAS are a subsequent
Gate, and native collaboration/product benefit are not claimed by this read slice.

G21 validation uses explicitly synthetic Host-controlled graph data. It is not
new real Agent/Oracle evidence. Production publishing and migration require the
separate trusted lifecycle implementation and review. The measured64×8 workload
and larger scale limits are disclosed in the maintainer validation report.
