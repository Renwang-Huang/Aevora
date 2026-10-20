"""Owned real graph controls/performance. All imported trusted records SYNTHETIC."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,time,uuid,resource,hashlib,statistics
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
from aevora.models import utc_now
from aevora.graph_queries import QUERIES
from aevora.experience_resolver import resolve_v2
from tools.validation.g21_fixture import seed,facts
E=Path(__file__).resolve().parent;OUT=E/'05_graph';OUT.mkdir(exist_ok=False)
def write(name,v):(OUT/name).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,default=lambda x:x.decode() if isinstance(x,bytes) else str(x))+'\n')
raw=(OUT/'RAW_CYPHER.jsonl').open('x');original=GraphRepository.query
count=0

def query(self,statement,params=None,*,read_only=True):
 global count
 t=time.monotonic();r=original(self,statement,params,read_only=read_only);count+=1
 raw.write(canonical_json(dict(graph=self.graph_name,query=statement,params=params,rows=r,read_only=read_only,elapsed=time.monotonic()-t))+'\n');raw.flush();return r
GraphRepository.query=query
main=GraphRepository.from_environment();kwargs=main._client.connection.connection_pool.connection_kwargs;main.close()
def new(name):
 r=GraphRepository(host='127.0.0.1',port=kwargs['port'],password=kwargs['password'],graph_name='aevora_v2_g21_proof_'+name)
 v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry());v.initialize();return v

def snapshot(v,name):
 nodes=v.transport.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id');edges=v.transport.query('MATCH(a)-[r]->(b) RETURN a.id,type(r),properties(r),b.id ORDER BY r.id')
 write(name,dict(graph=v.binding.graph_name,nodes=nodes,edges=edges,node_count=len(nodes),edge_count=len(edges),sha256=digest([nodes,edges])));return digest([nodes,edges])
truth=[];interventions=[]
for key,outcomes,current,expected in [('support',('PASS',),'sqlite_file','APPLY'),('unknown',('PASS',),None,'VERIFY'),('conflict',('PASS','FAIL'),'sqlite_file','VERIFY'),('counter',('FAIL',),'sqlite_file','ABSTAIN'),('infra',('ERROR',),'sqlite_file','VERIFY')]:
 v=new(key);data=seed(v,key,outcomes=outcomes);fs=facts(v.registry,task__shared_state_kind=current)
 before=snapshot(v,key+'-before.json');state,rows=resolve_v2(v,fs,'query:proof:'+key,utc_now());rec,w=rows[0]
 assert rec['core_verdict']==expected
 write(key+'-witness.json',w);write(key+'-recommendation.json',rec);write(key+'-registry.json',v.registry.__dict__)
 truth.append(dict(case=key,synthetic=True,independent_expected=expected,actual=rec['core_verdict'],reasons=rec['reason_codes'],manifest_sha256=digest(data['manifest']),witness_sha256=digest(w),graph_before_sha256=before,query_receipts=v.query_receipts))
 if key in {'support','conflict'}:
  relation='SUPPORTED_BY' if key=='support' else 'COUNTEREXAMPLE';item=next(e for e in data['edges'] if e['kind']==relation)
  v.transport.query('MATCH()-[r {id:$id}]->() DELETE r',dict(id=item['id']),read_only=False)
  cut=snapshot(v,key+'-cut.json')
  try:resolve_v2(v,fs,'query:proof:'+key,utc_now());raise AssertionError('Cut was not detected')
  except V2Error as error:assert error.code=='GRAPH_INTEGRITY_ERROR';code=error.code
  v.put_edge(item);restored=snapshot(v,key+'-restored.json');assert restored==before
  newrec=resolve_v2(v,fs,'query:proof:'+key,utc_now())[1][0][0];assert newrec==rec
  interventions.append(dict(case=key,relation=relation,edge_id=item['id'],before=expected,cut=code,restored=newrec['core_verdict'],before_graph_sha256=before,cut_graph_sha256=cut,restored_graph_sha256=restored))
 write(key+'-schema.json',v.schema_dump());v.transport.close()
write('TRUTH_TABLE.json',truth);write('INTERVENTIONS.json',interventions)
# Explicit target workload, no extrapolation to 100k/300k.
v=new('performance64x8')
for i in range(64):seed(v,'perf-'+str(i),outcomes=('PASS',)*8)
state=v.state();fs=facts(v.registry,task__shared_state_kind='sqlite_file');params=dict(tokens=['*',digest(['task.shared_state_kind','sqlite_file'])],after='',state=v.state_id,epoch=state['epoch'])
write('EXPLAIN.json',dict(query=QUERIES['Q01'],params=params,plan=str(v.transport._graph.explain(QUERIES['Q01'],params))))
write('PROFILE.json',dict(plan=str(v.transport._graph.profile(QUERIES['Q01'],params))))
write('PERFORMANCE_SCHEMA.json',v.schema_dump());snapshot(v,'performance-before.json')
measure=[]
for i in range(5):
 start=time.monotonic();prior=v.read_bytes;offset=len(v.query_receipts)
 try:
  st,rows=resolve_v2(v,fs,'query:perf:'+str(i),utc_now());result='COMPLETE';candidates=len(rows)
 except V2Error as error:result=error.code;candidates=None
 measure.append(dict(iteration=i,status=result,candidates=candidates,seconds=time.monotonic()-start,returned_bytes=v.read_bytes-prior,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
write('PERFORMANCE.json',dict(synthetic=True,dataset='64 relevant candidates x 8 paths',measurements=measure,observed_p95_seconds=sorted(m['seconds'] for m in measure)[-1],samples=5,scope='exploratory observed timings, not statistical SLO assurance',target_100k_300k='NOT_AT_TARGET',target_p95_5s='PASS_MEASURED_SCOPE' if all(m['status']=='COMPLETE' and m['seconds']<=5 for m in measure) else 'PERFORMANCE_LIMITED'))
write('DB_VERSION.json',dict(redis=v.transport._client.connection.info('server'),modules=v.transport._client.connection.execute_command('MODULE','LIST'),source='REAL_OWNED_AUTHENTICATED_DB',memory=v.transport._client.connection.info('memory')))
v.transport.close();raw.close();write('RECEIPT.json',dict(queries=count,raw_sha256=hashlib.sha256((OUT/'RAW_CYPHER.jsonl').read_bytes()).hexdigest(),new_agent_runs=0,new_independent_oracle_outcomes=0,synthetic=True))
print(json.dumps({'truth':len(truth),'interventions':len(interventions),'performance':measure}))
