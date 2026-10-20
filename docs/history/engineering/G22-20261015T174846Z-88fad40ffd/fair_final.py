from pathlib import Path
import sys,json,time,statistics,resource,hashlib,collections
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from aevora.graph_queries import QUERIES
E=Path(__file__).parent;label=sys.argv[1];O=E/'05_performance'/label;O.mkdir()
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_fair64x8')
registry=TrustRegistry(**json.loads((E/'00_baseline/performance-unprofiled/registry.json').read_text()))
if '--host-pins' in sys.argv:
 from aevora_maintainer.host_v2 import HostPins
 from aevora.host_pins import read_registry
 pin=HostPins(O/'private_host_pins')
 for category,values in registry.__dict__.items():
  for k,val in values.items():pin.put(category,k,val)
 registry=read_registry(pin.root)
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),registry);fs=json.loads((E/'00_baseline/performance-unprofiled/facts.json').read_text())
before=[r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),r.query('MATCH(a)-[r]->(b) RETURN a.id,type(r),properties(r),b.id ORDER BY r.id')]
measure=[]
for i in range(20):
 v.query_receipts=[];old=v.read_bytes;t=time.monotonic()
 state,rows=resolve_v2(v,fs,'query:fair-final:'+str(i),utc_now())
 measure.append(dict(iteration=i,seconds=time.monotonic()-t,status='COMPLETE',candidates=len(rows),bytes=v.read_bytes-old,query_receipts=v.query_receipts,witness_shas=[digest(w) for _,w in rows]))
 assert len(rows)==64
 (O/'measurements.json').write_text(json.dumps(measure));print(i,measure[-1]['seconds'],flush=True)
params=dict(ids=list(rows[0][1]['nodes']),relations=__import__('aevora.graph_queries',fromlist=['SEMANTIC_RELATIONS']).SEMANTIC_RELATIONS)
(O/'PLANS.json').write_text(json.dumps(dict(query=QUERIES['Q11'],params=params,explain=str(r._graph.explain(QUERIES['Q11'],params)),profile=str(r._graph.profile(QUERIES['Q11'],params))),indent=2))
after=[r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),r.query('MATCH(a)-[r]->(b) RETURN a.id,type(r),properties(r),b.id ORDER BY r.id')]
assert before==after
lat=sorted(x['seconds'] for x in measure)
(O/'RESULT.json').write_text(json.dumps(dict(source_module=sys.modules['aevora.graph_v2'].__file__,source_sha256=hashlib.sha256(Path(sys.modules['aevora.graph_v2'].__file__).read_bytes()).hexdigest(),samples=20,process_cold_first=True,database_cache='WARM',observed_p50=statistics.median(lat),observed_p95=lat[18],max=max(lat),not_statistical_slo=True,graph_sha256=digest(before),nodes=len(before[0]),edges=len(before[1]),graph_unchanged=True,host_pins='--host-pins' in sys.argv,returned_bytes=measure[0]['bytes'],rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),indent=2));r.close()
