MATCH(r:ExperienceRevision)-[s:SUPERSEDES]->(old:ExperienceRevision) WHERE r.id IN $ids OR old.id IN $ids RETURN properties(r),properties(s),properties(old) LIMIT 257
