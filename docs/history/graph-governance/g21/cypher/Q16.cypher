MATCH(n:V2Record {id:$id})-[:PUBLISHED_BY]->(m:PublicationManifest)<-[:COMMITS]-(s:TenantState {id:$state}) WHERE m.epoch<=$epoch RETURN m.id LIMIT 2
