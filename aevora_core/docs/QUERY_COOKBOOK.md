# Aevora executable Cypher cookbook

These are trusted-host reference queries for the actual FalkorDB schema.
MCP does not offer a Cypher endpoint. Supply values through `params`, never concatenate
Participant input into query text.

## Rule premises: a real relationship path

```cypher
MATCH (e:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)
      -[:USES_RULE]->(rule:Rule)-[:REQUIRES]->(p:Premise)
RETURN r.payload_json, rule.payload_json, p.payload_json
ORDER BY r.id, rule.id, p.id
```

The returned Premise facts drive WHEN. Deleting REQUIRES or USES_RULE edges in
an isolated ablation graph removes the condition evidence; the Python engine
does not restore premises from a strategy name.

## Support, conflict and observations: five actual hops

```cypher
MATCH (e:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)
      -[link]->(ev:Evidence)-[:VERIFIES]->(o:VerifiedOutcome)
      -[:IN_CONTEXT]->(c:Context)-[:FOR_TASK]->(t:Task)
WHERE type(link) IN $relations
RETURN type(link), r.payload_json, ev.payload_json, o.payload_json,
       c.payload_json, t.payload_json
ORDER BY r.id, ev.id, o.id, c.id, t.id, type(link)
```

Supply `$relations=["SUPPORTED_BY","COUNTEREXAMPLE","OBSERVED_OUTCOME"]`.
The trusted service projects these records through public allowlists before
providing WHY. Unknown Context facts remain null/missing; a run title or Episode
ID is not a condition substitute.

## Run-scoped query authority

```cypher
MATCH (q:Query)-[:CONSIDERED]->(e:Experience {id:$experience})
WHERE q.run_id=$run
RETURN count(q)
```

The MCP bridge fixes `$run` from its host-issued authority. A Participant cannot
claim that another Run queried or adopted an experience.

## Schema and reproducibility

```cypher
CALL db.constraints()
```

```cypher
MATCH (n)
RETURN labels(n), n.id, n.payload_sha256
ORDER BY n.id
```

```cypher
MATCH (s)-[r]->(t)
RETURN s.id, type(r), r.id, r.payload_sha256, t.id
ORDER BY s.id, type(r), r.id, t.id
```

The canonical digest over the actual node/edge rows identifies a graph state;
it is a local byte provenance measurement, not a third-party signed execution
attestation. Source references and raw observations remain distinct from third-party attestation.

## Explicit revision and governance paths

These queries use actual graph edges. Aggregated results order by projected
aliases. Order aggregated results by projected aliases.

```cypher
MATCH (:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)
OPTIONAL MATCH (r)-[:USES_RULE]->(rule:Rule)
RETURN r.payload_json AS record, r.payload_sha256 AS sha,
       collect(rule.id) AS rules
ORDER BY record
```

```cypher
MATCH (:Experience {id:$id})-[:HAS_REVISION]->(r:ExperienceRevision)
      -[s:SUPERSEDES]->(old:ExperienceRevision)
RETURN r.id, old.id, s.payload_json, s.payload_sha256
ORDER BY r.id, old.id
```

```cypher
MATCH (g:GovernanceEvent)
OPTIONAL MATCH (g)-[:GOVERNS]->(target)
RETURN g.payload_json AS record, g.payload_sha256 AS sha,
       collect([labels(target), target.id]) AS targets
ORDER BY record
```

The host validates canonical payloads, completion AuditEvents, declared typed
targets and explicit SUPERSEDES edges. Targets retain label and ID. There is no
created-time winner and no task identifier routing.

## Immutable Query replay

```cypher
MATCH (:Query {id:$source})-[r:AT_SNAPSHOT]->(:QuerySnapshot {id:$target})
RETURN r.id, r.payload_json, r.payload_sha256
```

The actual typed edge must have the endpoint-derived ID and valid payload hash.
The same helper validates CONSIDERED, DECIDED and RESPONDS_TO bindings used for
replay/feedback. Node content and immutable snapshot ID are validated separately.
A legacy Query has no invented snapshot; current evidence cannot substitute for
its unavailable historical body.

When recording query evidence, bind actual statements/parameters/results to
original line references. These are separate calls. Neither ordering nor FalkorDB's schema-cache version
makes this an atomic content snapshot.
