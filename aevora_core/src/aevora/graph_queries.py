"""Compiled read templates; no participant supplied Cypher, label or graph selector."""

QUERIES = {
    "Q16": "MATCH(n:V2Record {id:$id})-[:PUBLISHED_BY]->(m:PublicationManifest)<-[:COMMITS]-(s:TenantState {id:$state}) WHERE m.epoch<=$epoch RETURN m.id LIMIT 2",
    "Q00": "MATCH(s:TenantState {id:$state}) RETURN properties(s) LIMIT 2",
    "Q01": "MATCH(e:Experience) WHERE e.scope_token IN $tokens AND e.id>$after AND e.visibility='PUBLIC' MATCH(s:TenantState {id:$state})-[:COMMITS]->(m:PublicationManifest {experience_id:e.id}) WHERE m.epoch<=$epoch RETURN DISTINCT e.id ORDER BY e.id LIMIT 65",
    "Q02": "MATCH(e:Experience {id:$experience})-[h:HAS_REVISION]->(r:ExperienceRevision)-[u:USES_RULE]->(rule:Rule) OPTIONAL MATCH(rule)-[q:REQUIRES]->(p:Premise) RETURN properties(e),properties(h),properties(r),properties(u),properties(rule),properties(q),properties(p) LIMIT 1025",
    "Q03": "MATCH(r:ExperienceRevision)-[s:SUPERSEDES]->(old:ExperienceRevision) WHERE r.id IN $ids OR old.id IN $ids RETURN properties(r),properties(s),properties(old) LIMIT 257",
    "Q04": "MATCH(r:ExperienceRevision)-[link]->(ev:Evidence)-[v:VERIFIES]->(o:VerifiedOutcome)-[i:IN_CONTEXT]->(c:Context)-[f:FOR_TASK]->(t:Task), (o)-[a:ATTESTED_BY]->(authority:Authority) WHERE r.id IN $ids AND type(link) IN ['SUPPORTED_BY','COUNTEREXAMPLE','OBSERVED_OUTCOME'] RETURN properties(r),properties(link),properties(ev),properties(v),properties(o),properties(i),properties(c),properties(f),properties(t),properties(a),properties(authority) ORDER BY ev.id LIMIT 513",
    "Q05": "MATCH(g:GovernanceEvent)-[v:GOVERNS]->(t:V2Record) WHERE t.id IN $ids RETURN properties(g),properties(v),properties(t) LIMIT 257",
    "Q08": "MATCH(s:TenantState {id:$state}),(session:Session {id:$session}) RETURN properties(s),properties(session) LIMIT 2",
    "Q09": "MATCH(m:V2Record {id:$document})-[h:HAS_CHUNK]->(c:SnapshotChunk) RETURN properties(h),properties(c) ORDER BY c.chunk_index LIMIT 129",
    "Q10": "MATCH(n:V2Record) WHERE n.id IN $ids RETURN labels(n),properties(n) ORDER BY n.id LIMIT 8193",
    "Q11": "MATCH(a:V2Record)-[r]->(b:V2Record) WHERE a.id IN $ids AND type(r) IN $relations RETURN labels(a),a.id,type(r),properties(r),labels(b),b.id ORDER BY r.id LIMIT 8193 UNION MATCH(b:V2Record) WHERE b.id IN $ids WITH b MATCH(a:V2Record)-[r:GOVERNS]->(b) WHERE NOT a.id IN $ids RETURN labels(a),a.id,type(r),properties(r),labels(b),b.id ORDER BY r.id LIMIT 8193",
    "Q12": "MATCH(s:TenantState {id:$state})-[c:COMMITS]->(m:PublicationManifest {experience_id:$experience}) WHERE m.epoch<=$epoch RETURN properties(c),properties(m) ORDER BY m.epoch DESC LIMIT 257",
    "Q13": "MATCH(n:V2Record {id:$id}) RETURN labels(n),properties(n) LIMIT 2",
    "Q14": "MATCH(r:V2Record)-[p:PUBLISHED_BY]->(m:PublicationManifest {id:$manifest}) RETURN r.id,properties(p) ORDER BY r.id LIMIT 273",
}
SEMANTIC_RELATIONS = [
    "HAS_REVISION",
    "USES_RULE",
    "REQUIRES",
    "SUPPORTED_BY",
    "COUNTEREXAMPLE",
    "OBSERVED_OUTCOME",
    "VERIFIES",
    "IN_CONTEXT",
    "FOR_TASK",
    "ATTESTED_BY",
    "SUPERSEDES",
    "GOVERNS",
]
