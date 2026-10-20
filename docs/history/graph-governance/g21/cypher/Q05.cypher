MATCH(g:GovernanceEvent)-[v:GOVERNS]->(t:V2Record) WHERE t.id IN $ids RETURN properties(g),properties(v),properties(t) LIMIT 257
