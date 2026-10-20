from pathlib import Path
import json,time,hashlib,gzip,os,resource
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.models import utc_now
from aevora.experience_resolver import resolve_v2
from aevora.mcp_v2 import ReadGrant
from aevora.orderflow_outcome_bridge import TrustAnchor
from aevora_maintainer.host_v2 import TrustedHost,HostPins
from tools.validation.g22_fixture import ready
E=Path(__file__).parent;O=E/'05_performance/scale-acceptance-first';O.mkdir()
raw=gzip.open(O/'RAW_CYPHER.jsonl.gz','xt',compresslevel=3);original=GraphRepository.query

def write(name,value):(O/name).write_text(json.dumps(value,indent=2,sort_keys=True,default=str))
write('SOURCE_EPOCH.json',{str(p.relative_to(E/'worktree')):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['aevora_core/src','aevora_maintainer'] for p in (E/'worktree'/folder).rglob('*.py')})
def query(self,statement,params=None,*,read_only=True):
 t=time.monotonic();error=None;rows=[]
 try:rows=original(self,statement,params,read_only=read_only);return rows
 except Exception as ex:error=type(ex).__name__;raise
 finally:raw.write(canonical_json(dict(graph=self.graph_name,statement=statement,params=params,rows=rows,error=error,seconds=time.monotonic()-t))+'\n');raw.flush()
GraphRepository.query=query
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_scale100k300k')
v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry());pins=HostPins(O/'private_host_pins')
data=json.loads((E/'00_baseline/performance-before.json').read_text())
for labels,props in data['nodes']:
 n=decode(props,v.tenant)
 for category,kind in [('authorities','Authority'),('outcomes','VerifiedOutcome'),('publications','PublicationManifest')]:
  if n['kind']==kind:pins.put(category,n['id'],digest(n))
 if n['kind']=='Task':
  for f in n['facts'].values():pins.put('fact_sources',digest(f),f['authority_ref'])
v.registry=__import__('aevora.host_pins',fromlist=['read_registry']).read_registry(pins.root)
fs=json.loads((E/'00_baseline/performance-unprofiled/facts.json').read_text())
pins.put('fact_sources',digest(next(iter(fs.values()))),next(iter(fs.values()))['authority_ref'])
assert r.query('MATCH(n) RETURN count(n)')==[[100000]] and r.query('MATCH()-[e]->() RETURN count(e)')==[[300000]]
measure=[]
for i in range(5):
 t=time.monotonic();before=v.read_bytes;state,rows=resolve_v2(v,fs,'query:scale:'+str(i),utc_now())
 assert len(rows)==64 and all(w['completeness']=='COMPLETE' for rec,w in rows)
 measure.append(dict(seconds=time.monotonic()-t,bytes=v.read_bytes-before,candidates=len(rows),witness_shas=[digest(w) for _,w in rows]))
write('READS.json',measure)
gr=ReadGrant(v.tenant,'scale-run','scale-session','1',(datetime.now(timezone.utc)+__import__('datetime').timedelta(minutes=30)).isoformat(),authz_epoch=state['authz_epoch'])
v.put_node(record(v.tenant,'Session',[gr.run_id,gr.session_id,gr.generation],run_id=gr.run_id,session_id=gr.session_id,grant_generation=gr.generation,profile=PROFILE,state='ACTIVE',valid_until=gr.valid_until))
assert v.authorize(gr)==state
cases=json.loads((E/'01_admission/verified-runs/CASES.json').read_text());case=cases['cases'][0]
anchor=TrustAnchor(Path(case['root']),case['manifest_sha256'],{'evaluation_report.json':case['run_id']},profile='current_live',manifest_relative_path='HOST_RUN_MANIFEST.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],source_manifest_relative_path='SOURCE_MANIFEST.json')
grant=TrustedHost.bootstrap(v,pins.root,principal='scale-maintainer',allowed_scope={'task.shared_state_kind':['sqlite_file']})
h=TrustedHost(v,pins.root,grant);h.case=case;h.verifier=h.register_orderflow(anchor,case['evaluator_sha'],case['suite_sha'])
t=time.monotonic();c,review,prepared=ready(h,'g22-scale-real-oracle');prepare_seconds=time.monotonic()-t
t=time.monotonic();receipt=h.publish(prepared);publish_seconds=time.monotonic()-t
state,rows=resolve_v2(v,review['facts'],'query:scale-published',utc_now());assert len(rows)==65
rec,w=next(x for x in rows if x[0]['experience_id']==receipt['experience_id']);assert rec['core_verdict']=='APPLY'
revision=next(n for n in w['nodes'].values() if n['kind']=='ExperienceRevision')
t=time.monotonic();withdraw=h.govern(c['id'],review['id'],experience_id=receipt['experience_id'],target_id=revision['id'],event_type='withdraw',bounded_scope=review['approved_scope'],reason='Scale withdrawal read-after-write',request_key='scale-withdraw');withdraw_prepare_seconds=time.monotonic()-t
t=time.monotonic();h.publish(withdraw);withdraw_commit_seconds=time.monotonic()-t
state,rows=resolve_v2(v,review['facts'],'query:scale-withdrawn',utc_now());rec,w=next(x for x in rows if x[0]['experience_id']==receipt['experience_id']);assert rec['core_verdict']=='ABSTAIN'
try:v.chunks('QuerySnapshot','scale-over-limit',{'x':'a'*MAX_DOCUMENT});raise AssertionError('Oversized document accepted')
except V2Error as ex:assert ex.code=='CAPACITY_EXCEEDED';overflow=ex.code
from aevora.graph_queries import QUERIES
params=dict(tokens=['*',digest(['task.shared_state_kind','sqlite_file'])],state=v.state_id,after='',epoch=state['epoch'])
write('PLANS.json',dict(discovery=str(r._graph.explain(QUERIES['Q01'],params)),discovery_profile=str(r._graph.profile(QUERIES['Q01'],params)),neighbor=str(r._graph.explain(QUERIES['Q11'],dict(ids=list(w['nodes']),relations=__import__('aevora.graph_queries',fromlist=['SEMANTIC_RELATIONS']).SEMANTIC_RELATIONS)))))
write('RESULT.json',dict(status='PASS_DECLARED_GRAPH_SHAPE',initial_nodes=100000,initial_edges=300000,active_semantic_experiences=64,capacity_trace_nodes=96927,source='HOST_CONTROLLED_SCALE_FIXTURE_PLUS_FRESH_INDEPENDENT_HOST_RUN',new_agent_runs=0,real_host_run_id=case['run_id'],prepare_seconds=prepare_seconds,publish_seconds=publish_seconds,withdraw_prepare_seconds=withdraw_prepare_seconds,withdraw_commit_seconds=withdraw_commit_seconds,read_after_publish='APPLY',read_after_withdraw='ABSTAIN',overflow=overflow,counts_after=dict(nodes=r.query('MATCH(n) RETURN count(n)')[0][0],edges=r.query('MATCH()-[e]->() RETURN count(e)')[0][0]),memory=r._client.connection.info('memory'),rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,schema=v.schema_dump(),save=r._client.connection.save()))
raw.close();write('RAW_RECEIPT.json',dict(sha256=hashlib.sha256((O/'RAW_CYPHER.jsonl.gz').read_bytes()).hexdigest(),bytes=(O/'RAW_CYPHER.jsonl.gz').stat().st_size));r.close()
print('scale read/write/withdraw complete')
