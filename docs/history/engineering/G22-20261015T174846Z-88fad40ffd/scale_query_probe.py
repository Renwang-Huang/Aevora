from pathlib import Path
import json,time
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
from aevora.graph_queries import QUERIES,SEMANTIC_RELATIONS
E=Path(__file__).parent;O=E/'05_performance/query-probe';O.mkdir()
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close();r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_scale100k300k')
# One real active experience's complete manifest node IDs; not a fake timing query.
ms=r.query('MATCH(s:TenantState)-[:COMMITS]->(m:PublicationManifest) RETURN m.id ORDER BY m.epoch DESC LIMIT 1')[0][0]
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry());doc=v.load_document(v.node(ms));ids=list(doc['nodes'])
base=QUERIES['Q11'];prefix=base.split(' UNION ')[0]
variant=prefix+' UNION MATCH(b:V2Record) WHERE b.id IN $ids WITH b MATCH(a:V2Record)-[r:GOVERNS]->(b) WHERE NOT a.id IN $ids RETURN labels(a),a.id,type(r),properties(r),labels(b),b.id ORDER BY r.id LIMIT 8193'
results=[]
for name,q in [('current',base),('with_reverse_anchor',variant)]:
 params=dict(ids=ids,relations=SEMANTIC_RELATIONS);measure=[]
 for _ in range(5):t=time.monotonic();rows=r.query(q,params);measure.append(time.monotonic()-t)
 results.append(dict(name=name,statement=q,params=params,seconds=measure,rows=rows,explain=str(r._graph.explain(q,params)),profile=str(r._graph.profile(q,params))))
assert sorted(results[0]['rows'],key=lambda row:row[3]['id'])==sorted(results[1]['rows'],key=lambda row:row[3]['id'])
(O/'RESULT.json').write_text(json.dumps(dict(results=results,exact_complete_row_equality=True),indent=2));print([(r['name'],r['seconds']) for r in results]);r.close()
