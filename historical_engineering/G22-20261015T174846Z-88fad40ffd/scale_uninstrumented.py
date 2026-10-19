from pathlib import Path
import json,time,cProfile,pstats
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.models import utc_now
from aevora.experience_resolver import resolve_v2
from aevora.host_pins import read_registry
E=Path(__file__).parent;O=E/'05_performance/scale-uninstrumented';O.mkdir()
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_scale100k300k')
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),read_registry(E/'05_performance/scale-acceptance-first/private_host_pins'))
fs=json.loads((E/'00_baseline/performance-unprofiled/facts.json').read_text());measure=[]
for i in range(5):
 t=time.monotonic();before=v.read_bytes;v.query_receipts=[];st,rows=resolve_v2(v,fs,'query:scale-uninstrumented:'+str(i),utc_now())
 measure.append(dict(seconds=time.monotonic()-t,bytes=v.read_bytes-before,candidates=len(rows),queries=v.query_receipts,witness_shas=[digest(w) for _,w in rows]));(O/'measurements.json').write_text(json.dumps(measure));print(i,measure[-1]['seconds'],flush=True)
st=v.state();ids=v.discover(fs,st);pr=cProfile.Profile();pr.enable();v.read_witness(ids[0],st);pr.disable()
with (O/'one-witness-profile.txt').open('w') as f:pstats.Stats(pr,stream=f).sort_stats('cumtime').print_stats(60)
r.close()
