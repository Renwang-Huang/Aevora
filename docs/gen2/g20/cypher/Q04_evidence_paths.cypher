// PROPOSED v2 template; exact synthetic path-shape probe only, not production acceptance.
MATCH (s:TenantState {id:$state,tenant_id:$tenant})-[:COMMITS]->(m:PublicationManifest),
      (e:Experience {id:$experience,tenant_id:$tenant})-[:HAS_REVISION]->(r:ExperienceRevision)-[:PUBLISHED_BY]->(m),
      (r)-[link]->(ev:Evidence)-[:VERIFIES]->(o:VerifiedOutcome)-[:IN_CONTEXT]->(c:Context),
      (o)-[:ATTESTED_BY]->(a:Authority)
WHERE type(link) IN ['SUPPORTED_BY','COUNTEREXAMPLE','OBSERVED_OUTCOME']
  AND r.tenant_id=$tenant AND m.tenant_id=$tenant AND ev.tenant_id=$tenant
  AND o.tenant_id=$tenant AND c.tenant_id=$tenant AND a.tenant_id=$tenant
  AND m.epoch<=s.epoch AND a.kind='INDEPENDENT_ORACLE'
RETURN r.id,type(link),link.id,ev.id,o.id,o.verdict,c.id,a.id,m.id,s.epoch
ORDER BY r.id,ev.id,o.id,c.id,a.id
LIMIT 513
