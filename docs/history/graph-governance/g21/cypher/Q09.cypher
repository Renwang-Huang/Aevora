MATCH(m:V2Record {id:$document})-[h:HAS_CHUNK]->(c:SnapshotChunk) RETURN properties(h),properties(c) ORDER BY c.chunk_index LIMIT 129
