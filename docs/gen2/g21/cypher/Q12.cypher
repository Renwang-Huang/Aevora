MATCH(s:TenantState {id:$state})-[c:COMMITS]->(m:PublicationManifest {experience_id:$experience}) WHERE m.epoch<=$epoch RETURN properties(c),properties(m) ORDER BY m.epoch DESC LIMIT 257
