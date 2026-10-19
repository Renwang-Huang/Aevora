# Core Cypher actually used by Gen2

Source:`aevora_core/src/aevora/graph_queries.py`; execution entry:`GraphV2Repository.execute` in graph_v2.py. These are implemented bounded, parameterized templates, not proposed queries. Browser/Agent input never supplies the statement, graph or label.

## Q00

```cypher
MATCH(s:TenantState {id:$state}) RETURN properties(s) LIMIT 2
```

## Q01

```cypher
MATCH(e:Experience) WHERE e.scope_token IN $tokens AND e.id>$after AND e.visibility='PUBLIC' MATCH(s:TenantState {id:$state})-[:COMMITS]->(m:PublicationManifest {experience_id:e.id}) WHERE m.epoch<=$epoch RETURN DISTINCT e.id ORDER BY e.id LIMIT 65
```

## Q02

```cypher
MATCH(e:Experience {id:$experience})-[h:HAS_REVISION]->(r:ExperienceRevision)-[u:USES_RULE]->(rule:Rule) OPTIONAL MATCH(rule)-[q:REQUIRES]->(p:Premise) RETURN properties(e),properties(h),properties(r),properties(u),properties(rule),properties(q),properties(p) LIMIT 1025
```

## Q04

```cypher
MATCH(r:ExperienceRevision)-[link]->(ev:Evidence)-[v:VERIFIES]->(o:VerifiedOutcome)-[i:IN_CONTEXT]->(c:Context)-[f:FOR_TASK]->(t:Task), (o)-[a:ATTESTED_BY]->(authority:Authority) WHERE r.id IN $ids AND type(link) IN ['SUPPORTED_BY','COUNTEREXAMPLE','OBSERVED_OUTCOME'] RETURN properties(r),properties(link),properties(ev),properties(v),properties(o),properties(i),properties(c),properties(f),properties(t),properties(a),properties(authority) ORDER BY ev.id LIMIT 513
```

## Q05

```cypher
MATCH(g:GovernanceEvent)-[v:GOVERNS]->(t:V2Record) WHERE t.id IN $ids RETURN properties(g),properties(v),properties(t) LIMIT 257
```

## Q08

```cypher
MATCH(s:TenantState {id:$state}),(session:Session {id:$session}) RETURN properties(s),properties(session) LIMIT 2
```

## Q09

```cypher
MATCH(m:V2Record {id:$document})-[h:HAS_CHUNK]->(c:SnapshotChunk) RETURN properties(h),properties(c) ORDER BY c.chunk_index LIMIT 129
```

## Q11

```cypher
MATCH(a:V2Record)-[r]->(b:V2Record) WHERE a.id IN $ids AND type(r) IN $relations RETURN labels(a),a.id,type(r),properties(r),labels(b),b.id ORDER BY r.id LIMIT 8193 UNION MATCH(b:V2Record) WHERE b.id IN $ids WITH b MATCH(a:V2Record)-[r:GOVERNS]->(b) WHERE NOT a.id IN $ids RETURN labels(a),a.id,type(r),properties(r),labels(b),b.id ORDER BY r.id LIMIT 8193
```

## Q12

```cypher
MATCH(s:TenantState {id:$state})-[c:COMMITS]->(m:PublicationManifest {experience_id:$experience}) WHERE m.epoch<=$epoch RETURN properties(c),properties(m) ORDER BY m.epoch DESC LIMIT 257
```

## Q16

```cypher
MATCH(n:V2Record {id:$id})-[:PUBLISHED_BY]->(m:PublicationManifest)<-[:COMMITS]-(s:TenantState {id:$state}) WHERE m.epoch<=$epoch RETURN m.id LIMIT 2
```

Q00 reads the tenant fence; Q01 discovers scoped published candidates; Q02 reads rule prerequisites; Q04 reads independent evidence/Outcome/Authority paths; Q05 reads governance; Q08 rechecks permission; Q09 reconstructs chunked documents; Q11 checks complete relationships; Q12/Q16 validate committed publication. Parameters such as `$state`, `$epoch`, `$tokens`, `$ids`, `$experience` are selected by the trusted repository. `LIMIT` overflow fails closed. Production Q07 publication uses the included Trusted Host implementation with explicitly registered authority and protected credentials; the public synthetic seed is not advertised as production Q07 admission.
