// PROPOSED / NOT_EXECUTED; Host params only; payload/manifest verification is mandatory.
MATCH (e:Experience {id:$experience,tenant_id:$tenant})-[:HAS_REVISION]->(r:ExperienceRevision)-[link:SUPERSEDES]->(old:ExperienceRevision) WHERE r.tenant_id=$tenant AND old.tenant_id=$tenant RETURN r.id,old.id,link.id,link.payload_json,link.payload_sha256 ORDER BY r.id,old.id LIMIT 1025
