"""Comparable semantic-background capacity fixture. No real Agent/Outcome claim."""
from pathlib import Path
import json,time,gzip,hashlib
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.models import utc_now
from tools.validation.g21_fixture import bulk,seed
E=Path(__file__).parent;O=E/'05_performance/semantic-scale-seed';O.mkdir()
raw=gzip.open(O/'RAW_CYPHER.jsonl.gz','xt',compresslevel=2);original=GraphRepository.query
counter=0

def query(self,statement,params=None,*,read_only=True):
 global counter
 t=time.monotonic();rows=[];error=None
 try:rows=original(self,statement,params,read_only=read_only);return rows
 except Exception as ex:error=type(ex).__name__;raise
 finally:
  counter+=1;raw.write(canonical_json(dict(graph=self.graph_name,statement=statement,params=params,rows=rows,error=error,seconds=time.monotonic()-t))+'\n');raw.flush()
GraphRepository.query=query
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_semantic100k300k')
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry());v.initialize()
data=json.loads((E/'00_baseline/performance-before.json').read_text());nodes=[decode(p,v.tenant) for _,p in data['nodes']];edges=[decode(p,v.tenant) for _,_,p,_ in data['edges']]
r.query('MATCH(s:TenantState) SET s=$p',dict(p=native(next(n for n in nodes if n['kind']=='TenantState'))),read_only=False);bulk(v,nodes,edges)
for n in nodes:
 if n['kind']=='Authority':v.registry.authorities[n['id']]=digest(n)
 if n['kind']=='VerifiedOutcome':v.registry.outcomes[n['id']]=digest(n)
 if n['kind']=='PublicationManifest':v.registry.publications[n['id']]=digest(n)
 if n['kind']=='Task':
  for f in n['facts'].values():v.registry.fact_sources[digest(f)]=f['authority_ref']
kinds=['postgresql','redis','mysql','shared_memory','s3','file_store','mongodb','distributed_kv'];t=time.monotonic()
for i in range(1984):
 seed(v,'semantic-background-'+str(i),scope_value=kinds[i%8],required={'task.shared_state_kind':[kinds[i%8]]},outcomes=('PASS',)*7+('FAIL',))
 if i%64==0:print('background experiences',i+1,flush=True)
(O/'REGISTRY.json').write_text(json.dumps(v.registry.__dict__,sort_keys=True))
count=r.query('MATCH(n) RETURN count(n)')[0][0];assert count<=100000,count
extra=100000-count;created=utc_now();common=','.join(k+':row.'+k for k in sorted(COMMON|{'payload_json','payload_sha256'}))
for offset in range(0,extra,256):
 ns=[record(v.tenant,'ToolEvent',['semantic-scale-trace',i],created=created,source='HOST_CONTROLLED_SCALE_FIXTURE',event_type='CAPACITY_HISTORY_TRACE',sequence=i) for i in range(offset,min(offset+256,extra))]
 r.query(f'UNWIND $rows AS row CREATE(n:V2Record:ToolEvent {{{common}}}) SET n += row RETURN count(n)',dict(rows=[native(n) for n in ns]),read_only=False)
# Preserve all active64 semantic witnesses. Background citations exercise the
# complete global indexes and relationship store, without forging support links.
ids=[(x[0],x[1]) for x in r.query("MATCH(n:V2Record) WHERE n.source_type='HOST_CONTROLLED_SCALE_FIXTURE' OR n.scope_token IN $tokens RETURN n.id,n.kind ORDER BY n.id",dict(tokens=[digest(['task.shared_state_kind',k]) for k in kinds]))]
# Use only background experiences/rules/traces for cross references; no citation
# is classified as SUPPORT or COUNTEREXAMPLE.
assert len(ids)>2048,len(ids)
needed=300000-r.query('MATCH()-[e]->() RETURN count(e)')[0][0]
for offset in range(0,needed,256):
 es=[]
 for j in range(offset,min(offset+256,needed)):
  i=j%len(ids);step=1+j//len(ids);a_id,a_kind=ids[i];b_id,b_kind=ids[(i+step)%len(ids)]
  es.append(edge(v.tenant,'CITES',dict(id=a_id,kind=a_kind,tenant_id=v.tenant),dict(id=b_id,kind=b_kind,tenant_id=v.tenant),created=created,fixture_source='HOST_CONTROLLED_SCALE_FIXTURE'))
 r.query(f'UNWIND $rows AS row MATCH(a:V2Record {{id:row.source_id}}),(b:V2Record {{id:row.target_id}}) CREATE(a)-[e:CITES {{{common}}}]->(b) SET e += row RETURN count(e)',dict(rows=[native(e) for e in es]),read_only=False)
 if offset%10240==0:print('citation edges',offset+len(es),flush=True)
counts=dict(nodes=r.query('MATCH(n) RETURN count(n)')[0][0],edges=r.query('MATCH()-[e]->() RETURN count(e)')[0][0]);assert counts==dict(nodes=100000,edges=300000)
result=dict(counts=counts,experience_count=r.query('MATCH(e:Experience) RETURN count(e)')[0][0],scope_counts=r.query('MATCH(e:Experience) RETURN e.scope_token,count(e)'),node_distribution=r.query('MATCH(n) RETURN labels(n),count(n)'),edge_distribution=r.query('MATCH()-[e]->() RETURN type(e),count(e)'),seconds=time.monotonic()-t,source='HOST_CONTROLLED_SYNTHETIC_CAPACITY_FIXTURE',background_outcome_paths=1984*8,target_related_candidates=64,target_paths_each=8,schema=v.schema_dump(),memory=r._client.connection.info('memory'),save=r._client.connection.save(),queries=counter)
raw.close();result['raw_sha256']=hashlib.sha256((O/'RAW_CYPHER.jsonl.gz').read_bytes()).hexdigest();(O/'RESULT.json').write_text(json.dumps(result,indent=2,default=str));print(counts);r.close()
