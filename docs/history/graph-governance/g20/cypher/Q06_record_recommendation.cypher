// PROPOSED / NOT_EXECUTED. Trusted service params only; UNIQUE(id) checked before write.
MATCH (s:TenantState {id:$state,tenant_id:$tenant})
WHERE s.epoch=$epoch AND s.authz_epoch=$authz_epoch
MERGE (n:Recommendation {id:$id,tenant_id:$tenant,record_version:$record_version,
 kind:'Recommendation',payload_json:$payload,payload_sha256:$sha,created_at:$created,
 source_type:'core_derived',authority_ref:$authority,visibility:'PUBLIC'})
ON CREATE SET n.run_id=$run,n.query_id=$query,n.experience_id=$experience,
 n.semantic_epoch=$epoch,n.core_verdict=$verdict,n.policy_version=$policy
RETURN n.payload_sha256,n.semantic_epoch
