"""Actual 100k/300k owned capacity fixture, NOT real Agent engineering outcomes."""
from pathlib import Path
import json,time,gzip,hashlib,collections,os
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.models import utc_now
from tools.validation.g21_fixture import bulk
E=Path(__file__).parent;O=E/'05_performance/scale-seed';O.mkdir()
raw=gzip.open(O/'SEED_CYPHER.jsonl.gz','xt',compresslevel=3);original=GraphRepository.query
counter=0

def query(self,statement,params=None,*,read_only=True):
 global counter
 start=time.monotonic()
 try:
  rows=original(self,statement,params,read_only=read_only);status='RETURNED';return rows
 except Exception as ex:
  status=type(ex).__name__;rows=[];raise
 finally:
  counter+=1;raw.write(canonical_json(dict(graph=self.graph_name,statement=statement,params=params,rows=rows,status=status,elapsed=time.monotonic()-start))+'\n');raw.flush()
GraphRepository.query=query
main=GraphRepository.from_environment();kw=main._client.connection.connection_pool.connection_kwargs;main.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_scale100k300k')
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry());v.initialize()
data=json.loads((E/'00_baseline/performance-before.json').read_text())
# Replace only the newly initialized state with the exact archived synthetic state;
# this is fixture creation on a fresh owned DB, never a production publication.
nodes=[decode(p,v.tenant) for _,p in data['nodes']];edges=[decode(p,v.tenant) for _,_,p,_ in data['edges']]
state=next(n for n in nodes if n['kind']=='TenantState')
r.query('MATCH(s:TenantState) SET s=$p',dict(p=native(state)),read_only=False)
bulk(v,nodes,edges)
created=utc_now();filler_count=100000-len(nodes)
common=','.join(k+':row.'+k for k in sorted(COMMON|{'payload_json','payload_sha256'}))
t=time.monotonic()
for offset in range(0,filler_count,512):
 ns=[record(v.tenant,'ToolEvent',['scale-event',i],created=created,source='HOST_CONTROLLED_SCALE_FIXTURE',event_type='ARCHIVED_TRACE_CAPACITY',sequence=i,scope_class='IRRELEVANT_TO_ACTIVE_EXPERIENCES') for i in range(offset,min(offset+512,filler_count))]
 r.query(f'UNWIND $rows AS row CREATE(n:V2Record:ToolEvent {{{common}}}) SET n += row RETURN count(n)',dict(rows=[native(n) for n in ns]),read_only=False)
 if offset%10240==0:print('nodes',offset+len(ns),flush=True)
ids=[identity(v.tenant,'ToolEvent',['scale-event',i]) for i in range(filler_count)]
needed=300000-len(edges)
for offset in range(0,needed,512):
 es=[]
 for index in range(offset,min(offset+512,needed)):
  i=index%filler_count;step=[1,17,191,307][index//filler_count]
  a=dict(id=ids[i],kind='ToolEvent',tenant_id=v.tenant);b=dict(id=ids[(i+step)%filler_count],kind='ToolEvent',tenant_id=v.tenant)
  es.append(edge(v.tenant,'CITES',a,b,created=created,source='HOST_CONTROLLED_SCALE_FIXTURE'))
 r.query(f'UNWIND $rows AS row MATCH(a:V2Record {{id:row.source_id}}),(b:V2Record {{id:row.target_id}}) CREATE(a)-[rel:CITES {{{common}}}]->(b) SET rel += row RETURN count(rel)',dict(rows=[native(e) for e in es]),read_only=False)
 if offset%20480==0:print('edges',offset+len(es),flush=True)
counts=dict(nodes=r.query('MATCH(n) RETURN count(n)')[0][0],edges=r.query('MATCH()-[r]->() RETURN count(r)')[0][0])
assert counts==dict(nodes=100000,edges=300000)
result=dict(source='HOST_CONTROLLED_SCALE_FIXTURE',active_semantic_nodes=len(nodes),active_semantic_edges=len(edges),counts=counts,seconds=time.monotonic()-t,distribution=r.query('MATCH(n) RETURN labels(n),count(n)'),edge_distribution=r.query('MATCH()-[r]->() RETURN type(r),count(r)'),schema=v.schema_dump(),memory=r._client.connection.info('memory'),queries=counter,save=r._client.connection.save())
raw.close();result['raw_sha256']=hashlib.sha256((O/'SEED_CYPHER.jsonl.gz').read_bytes()).hexdigest();(O/'RESULT.json').write_text(json.dumps(result,indent=2,default=str));r.close();print(json.dumps(counts))
