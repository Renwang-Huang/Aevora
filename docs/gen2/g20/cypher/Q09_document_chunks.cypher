// PROPOSED / NOT_EXECUTED. Authorized query/publication manifests only, never arbitrary client-provided ID.
MATCH (m)-[h:HAS_CHUNK]->(c:SnapshotChunk)
WHERE m.id=$manifest AND m.tenant_id=$tenant AND c.tenant_id=$tenant
RETURN h.id,h.payload_json,h.payload_sha256,c.id,c.chunk_index,c.payload_json,c.payload_sha256
ORDER BY c.chunk_index
LIMIT 129
