// TEST-ONLY minimal commit-fence shape. Full lifecycle commit is Q07 in the contracts document.
MATCH (s:TenantState {id:$state,tenant_id:$tenant}),
      (m:PublicationManifest {id:$manifest,tenant_id:$tenant})
WHERE s.epoch=$expected AND m.epoch=$next
CREATE (s)-[:COMMITS {id:$edge,tenant_id:$tenant}]->(m)
SET s.epoch=$next
RETURN s.epoch,m.id
