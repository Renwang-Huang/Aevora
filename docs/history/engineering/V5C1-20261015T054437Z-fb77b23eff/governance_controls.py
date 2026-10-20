from pathlib import Path
import sys,os,json,uuid,tempfile,secrets,datetime
from contextlib import contextmanager
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.checkpoint import capture_graph
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.mcp_broker import MCPBroker
from aevora.mcp_server import PublicContextClaims
from integrations.aevora import public_runtime_context
from scripts.aevora_h2_security import RPCClient
from scripts.aevora_h2_graph_e2e import RawCommands
from aevora.historical_import import ATOMIC_ID,LOCK_ID
out=E/'03_regression/governance_retry1';out.mkdir();main=GraphRepository.from_environment();original=main.state_fingerprint();name='aevora_v5c1_governance_'+uuid.uuid4().hex;main._graph.copy(name);os.environ['AEVORA_FALKORDB_GRAPH']=name;r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);checks=[]
eid='experience:published:4cfa3b4cf946f4b43a3d06a7c950b77dfd52040f4abedd96f0969dfc9fee91a1'
def check(label,ok,observed):
 row={'name':label,'status':'PASS' if ok else 'FAIL','at':now(),'observed':observed,'actor':'TRUSTED_HOST_CONTROL_NOT_AGENT'};checks.append(row)
 with (out/'checks.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 assert ok,label
@contextmanager
def wire(label,facts):
 with tempfile.TemporaryDirectory(prefix='v5c1-neg-') as td:
  token=secrets.token_hex(32);b=MCPBroker(run_id='v5c1-neg-'+uuid.uuid4().hex,public_context=facts,socket_path=Path(td)/'mcp.sock',run_token=token,event_path=out/(label+'_mcp.jsonl'),enable_proposals=True)
  with b:
   c=RPCClient(b,token,out/(label+'_client.jsonl'));c.initialize()
   try:yield c,b
   finally:c.close()
  write(out/(label+'_cleanup.json'),b.metadata)
def query(c):
 reply=c.tool('resolve_experience',{'task_context':{}});assert reply and not reply['result'].get('isError');return reply['result']['structuredContent']
def byid(q,key):return next(v for v in q['candidates'] if v['experience_id']==key)
def denied(c,label,tool,args):
 before=r.state_fingerprint();reply=c.tool(tool,args);check(label,reply and reply['result'].get('isError') is True and r.state_fingerprint()==before,reply)
contexts={ep:public_runtime_context(json.loads((E/'owned_runtime/source/benchmark/scenarios'/ep/'public.json').read_text())) for ep in ['A','D','D-V02']}
try:
 write(out/'complete_graph_before.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 with wire('full_d',contexts['D']) as (c,b):
  q=query(c);write(out/'full_d_result.json',q)
  for key,want in [(ATOMIC_ID,'APPLY'),(LOCK_ID,'ABSTAIN'),(eid,'APPLY')]:check('full_d_'+key,byid(q,key)['decision']==want,byid(q,key))
  tools=c.call('tools/list')['result']['tools'];schema=next(v['inputSchema'] for v in tools if v['name']=='resolve_experience')
  check('actual_four_tools_and_schema',len(tools)==4 and schema['properties']['task_context']['properties']==PublicContextClaims.model_json_schema()['properties'],[v['name'] for v in tools])
  for label,args in [('oversized_context',{'task_context':{'observed_failure_mode':'汉'*4000}}),('nested_context',{'task_context':{'concurrency_scope':{'private-marker':'value'}}}),('unknown_field',{'task_context':{'oracle_answer':'private-marker'}})]:denied(c,label,'resolve_experience',args)
  denied(c,'forged_decision_outcome','record_decision',{'decision':{'query_id':q['query_id'],'experience_id':eid,'decision':'APPLY','reason':'Forbidden authority negative control','verified':True}})
  denied(c,'foreign_query','build_evidence_bundle',{'experience_id':eid,'query_id':'query:foreign:unavailable'})
  denied(c,'forged_cursor','build_evidence_bundle',{'experience_id':eid,'query_id':q['query_id'],'cursor':'forged-local-cursor'})
  before=r.state_fingerprint();bad=RPCClient(b,'invalid-scoped-capability',out/'wrong_auth.jsonl');check('wrong_auth_denied',bad.ack.get('aevora_transport')=='REJECTED' and r.state_fingerprint()==before,bad.ack);bad.close()
 with wire('unknown',{}) as (c,b):
  q=query(c);check('unknown_facts_verify',all(byid(q,key)['decision']=='VERIFY' for key in [ATOMIC_ID,LOCK_ID,eid]),q)
 with wire('a',contexts['A']) as (c,b):
  q=query(c);check('thread_positive_and_scope_refusal',byid(q,LOCK_ID)['decision']=='APPLY' and byid(q,eid)['decision']=='ABSTAIN',q)
 with wire('lease',contexts['D-V02']) as (c,b):
  q=query(c);write(out/'lease_old_competitor_baseline.json',q);check('lease_current_scope_not_silently_covered',all(byid(q,key)['decision']!='APPLY' for key in [ATOMIC_ID,eid]),q)
 for label,tool in [('host_publish','publish_experience'),('host_review','review_candidate')]:
  with wire(label,contexts['D']) as (c,b):
   before=r.state_fingerprint();reply=c.tool(tool,{});check(label+'_denied',reply is None and b.metadata['rejections'].get('TOOL_NOT_ALLOWED')==1 and r.state_fingerprint()==before,{'reply':reply,'metadata':b.metadata})
 baseline=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION)
 rid,pid,kid,payload,fingerprint=r.query('MATCH(e:Experience {id:$id})-[:HAS_REVISION]->(:ExperienceRevision)-[:USES_RULE]->(x:Rule)-[k:REQUIRES]->(p:Premise) RETURN x.id,p.id,k.id,k.payload_json,k.payload_sha256 ORDER BY k.id LIMIT 1',{'id':eid})[0]
 try:
  r.query('MATCH()-[k:REQUIRES {id:$id}]->() DELETE k',{'id':kid},read_only=False)
  with wire('edge_cut',contexts['D']) as (c,b):
   q=query(c);check('edge_cut_refuses_apply',byid(q,eid)['decision']=='VERIFY' and bool(byid(q,eid)['graph_integrity_issues']),byid(q,eid))
 finally:r.put_edge('REQUIRES','Rule',rid,'Premise',pid,json.loads(payload))
 restored=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);originaledges={v[2]:v for v in baseline['edges']};newedges={v[2]:v for v in restored['edges']}
 check('original_edges_exactly_restored',all(newedges.get(key)==value for key,value in originaledges.items()),{'edge_id':kid,'original_count':len(originaledges),'now':len(newedges)})
 with wire('edge_restored',contexts['D']) as (c,b):check('edge_restore_recovers_apply',byid(query(c),eid)['decision']=='APPLY',eid)
 # Explicit synthetic governance conflict, on this full isolated copy only.
 r.attach_evidence(ATOMIC_ID,{'id':'evidence:v5c1-negative-conflict','source_type':'synthetic_or_test_fixture','source_run_id':'v5c1-conflict','public_summary':'EXPLICIT SYNTHETIC GOVERNANCE NEGATIVE CONTROL'},
  {'id':'outcome:v5c1-negative-conflict','run_id':'v5c1-conflict','submission_digest':'a'*64,'evaluator_fingerprint':'b'*64,'test_suite_fingerprint':'c'*64,'verifier_identity':'SYNTHETIC_GOVERNANCE_CONTROL','verdict':'FAIL'},
  {'id':'context:v5c1-negative-conflict','facts':contexts['D']},{'id':'task:v5c1-negative-conflict','public_title':'Synthetic conflict control'},relation='COUNTEREXAMPLE')
 with wire('conflict',contexts['D']) as (c,b):check('real_graph_conflict_refuses_apply',byid(query(c),ATOMIC_ID)['decision']=='VERIFY',ATOMIC_ID)
 life=CandidateLifecycle(r);candidate=r.get_node('Experience',eid)['publication_candidate_id'];view=life.inspect(candidate)
 grant=ReviewGrant('v5c1-control-only-host',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=20)).isoformat())
 life.transition(candidate,'WITHDRAWN',expected_head_sha256=view['head_sha256'],event_key='v5c1-withdraw-copy-only',reason='Explicit controlled withdrawal on isolated full graph copy',grant=grant)
 with wire('withdrawn',contexts['D']) as (c,b):check('withdrawn_not_returned',eid not in [v['experience_id'] for v in query(c)['candidates']],eid)
 before=r.state_fingerprint();copied=E/'00_baseline/historical_native_receipt';anchor=TrustAnchor(copied,'0'*64,{'evaluation_report.json':copied.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_archive_root=E/'source',source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json',source_manifest_sha256='0'*64,source_snapshot_relative_path='frozen_source_snapshot')
 try:verify_outcome(anchor,'evaluation_report.json');raise AssertionError('forged pin accepted')
 except ValueError as error:check('forged_host_outcome_pin_refused',r.state_fingerprint()==before,{'error_type':type(error).__name__,'reason':str(error)})
 previous=os.environ['AEVORA_FALKORDB_PORT'];os.environ['AEVORA_FALKORDB_PORT']='17719'
 try:
  with wire('connection_refused',contexts['D']) as (c,b):
   reply=c.tool('resolve_experience',{'task_context':{}});check('db_refusal_explicit_not_fallback',reply['result'].get('isError') is True and 'AEVORA_GRAPH_UNAVAILABLE' in json.dumps(reply),reply)
 finally:os.environ['AEVORA_FALKORDB_PORT']=previous
 with wire('connection_restored',contexts['D']) as (c,b):check('new_connection_after_restore_queries_live',query(c)['status']=='AVAILABLE','actual live SDK query')
 check('original_full_graph_untouched',main.state_fingerprint()==original,main.state_fingerprint())
 write(out/'complete_graph_after.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 write(out/'RESULT.json',{'status':'PASS','at':now(),'checks':checks,'model_requests':0,'full_graph_no_initial_edge_removal':True,'scope':'REAL SDK/UDS/DB Host controls; synthetic conflict explicitly labeled; no Agent result'})
 print('FULL_GRAPH_GOVERNANCE_CONTROLS_PASS',len(checks),flush=True)
finally:raw.close();r.close();main.close()
