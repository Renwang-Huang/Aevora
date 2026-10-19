from pathlib import Path
import json,time,resource,sys,collections,cProfile,pstats,hashlib
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from tools.validation.g21_fixture import bulk,facts
E=Path(__file__).parent
out=E/'05_performance/optimized-first';out.mkdir(exist_ok=False)
data=json.loads((E/'00_baseline/performance-before.json').read_text())
r=GraphRepository.from_environment();kw=r._client.connection.connection_pool.connection_kwargs;r.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_fair64x8')
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry())
nodes=[decode(x[1],v.tenant) for x in data['nodes']];edges=[decode(x[2],v.tenant) for x in data['edges']]
v.initialize()
for n in nodes:
 if n['kind']=='Authority':v.registry.authorities[n['id']]=digest(n)
 if n['kind']=='VerifiedOutcome':v.registry.outcomes[n['id']]=digest(n)
 if n['kind']=='PublicationManifest':v.registry.publications[n['id']]=digest(n)
 if n['kind']=='Task':
  for f in n['facts'].values():v.registry.fact_sources[digest(f)]=f['authority_ref']
fs=facts(v.registry,task__shared_state_kind='sqlite_file')
(out/'source.json').write_text(json.dumps({'module':sys.modules['aevora.graph_v2'].__file__,'snapshot_sha256':hashlib.sha256((E/'00_baseline/performance-before.json').read_bytes()).hexdigest(),'nodes':len(nodes),'edges':len(edges)}))
measure=[]
for i in range(5):
 v.query_receipts=[];v.read_bytes=0;t=time.monotonic();pr=cProfile.Profile()
 st,rr=resolve_v2(v,fs,'query:fair:'+str(i),utc_now())
 seconds=time.monotonic()-t;assert len(rr)==64
 row={'seconds':seconds,'bytes':v.read_bytes,'queries':v.query_receipts,'candidate_witness_shas':[digest(w) for _,w in rr]};measure.append(row)
 (out/'measurements.json').write_text(json.dumps(measure))
 print(i,seconds,flush=True)
(out/'registry.json').write_text(json.dumps(v.registry.__dict__))
(out/'facts.json').write_text(json.dumps(fs));r.close()

v.query_receipts=[];st=v.state();ids=v.discover(fs,st);pr=cProfile.Profile();pr.enable();v.read_witness(ids[0],st);pr.disable()
with (out/'one-witness-profile.txt').open('w') as f:pstats.Stats(pr,stream=f).sort_stats('cumtime').print_stats(60)
