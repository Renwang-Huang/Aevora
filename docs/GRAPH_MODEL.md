# Graph v2 model

Runtime contracts are`aevora.graph/2.0.0-rc2`,`aevora.mcp/2.0.0-rc2` and
`aevora.whenwhy/2.0.0-rc2`; these are release-candidate contracts, not a claim of
stable v2.0 GA. Source:`aevora_core/src/aevora/contracts.py`,schemas_v2 and graph_queries.py.

- Experience is the stable identity; immutable ExperienceRevision selects Rule.
- Rule → REQUIRES → Premise records phase, necessary/exclusion mode, exact typed
  values and scope. An unknown required fact leads to VERIFY, not inferred truth.
- Revision → SUPPORTED_BY/COUNTEREXAMPLE → Evidence → VERIFIES → VerifiedOutcome
  → ATTESTED_BY → Authority. Context and Task establish the evidence's scope.
- GovernanceEvent → GOVERNS → Revision/Evidence expresses withdrawal, supersession
  or scoped change; historical records are retained.
- PublicationManifest declares the complete node/edge closure. TenantState,
  COMMITS, authenticated discovery catalogue and epochs fence visibility.
- Query/QuerySnapshot/Recommendation/Decision record a bounded read and an
  untrusted Agent claim. Candidate remains PROPOSED_UNTRUSTED until Host review.

`created_at` is not a permission grant. Trusted pins, phase provenance, complete
manifests and actual graph paths are all required. Agent text cannot mint a
known premise, independent outcome or Host authority. Necessary and exclusion
predicates can coexist on one fact; their `(mode,fact_key)` pairs are distinct.

The public demo has its own tenant, graph namespace, synthetic pins and actual
public verifier result. It deliberately grants no production authority. Its
withdrawn and baseline graph states are separate controlled examples; they are
not new Native Agent sessions or a causal treatment experiment.
