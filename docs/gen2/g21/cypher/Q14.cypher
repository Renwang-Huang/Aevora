MATCH(r:V2Record)-[p:PUBLISHED_BY]->(m:PublicationManifest {id:$manifest}) RETURN r.id,properties(p) ORDER BY r.id LIMIT 273
