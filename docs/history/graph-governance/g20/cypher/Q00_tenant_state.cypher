// PROPOSED / NOT_EXECUTED; Host params only; payload/manifest verification is mandatory.
MATCH (s:TenantState {id:$state,tenant_id:$tenant}) RETURN s.generation,s.epoch,s.authz_epoch,s.schema_version,s.policy_version,s.payload_sha256 LIMIT 2
