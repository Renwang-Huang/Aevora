"""Actual owned Graph + authenticated official MCP controls, not model behavior."""
from pathlib import Path
import sys,json,os,uuid,tempfile,secrets,datetime
from contextlib import contextmanager
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.admission import verify_orderflow_candidate
from aevora.orderflow_outcome_bridge import TrustAnchor
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.experience_resolver import ExperienceResolver
from aevora.historical_import import ATOMIC_ID,LOCK_ID
from integrations.aevora import public_runtime_context
from aevora.mcp_broker import MCPBroker
from scripts.aevora_h2_security import RPCClient
from scripts.aevora_h2_graph_e2e import RawCommands
out=E/'05_negative_controls/governance_retry2';out.mkdir();main=GraphRepository.from_environment();original=main.state_fingerprint();name='aevora_v5c_control_'+uuid.uuid4().hex
main._graph.copy(name);os.environ['AEVORA_FALKORDB_GRAPH']=name;r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);checks=[]
eid=json.loads((E/'03_feedback/S2_SELECTION.json').read_text())['new_published_experience_id']
def check(n,ok,observed):
 row={'name':n,'status':'PASS' if ok else 'FAIL','observed':observed,'at':now(),'actor':'TRUSTED_HOST_CONTROL_NOT_AGENT'};checks.append(row)
 with (out/'checks.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 if not ok:raise AssertionError(n)
@contextmanager
def wire(label,context):
 with tempfile.TemporaryDirectory(prefix='v5c-control-') as d:
  token=secrets.token_hex(32);b=MCPBroker(run_id='v5c-control-'+uuid.uuid4().hex,public_context=context,socket_path=Path(d)/'mcp.sock',run_token=token,event_path=out/(label+'_mcp.jsonl'),enable_proposals=True)
  with b:
   c=RPCClient(b,token,out/(label+'_client.jsonl'));c.initialize()
   try:yield c,b
   finally:c.close()
  write(out/(label+'_cleanup.json'),b.metadata)
def resolve(c):
 result=c.tool('resolve_experience',{'task_context':{}});assert not result['result'].get('isError');return result['result']['structuredContent']
def byid(v,i):return next(x for x in v['candidates'] if x['experience_id']==i)
def noauthority(label,c,tool,args):
 before=r.state_fingerprint();reply=c.tool(tool,args);check(label,reply['result'].get('isError') is True and r.state_fingerprint()==before,reply)
try:
 write(out/'graph_before_preregistration_subset.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 # Explicit isolated control: reproduce the corpus that S2 actually queried,
 # excluding ONLY the later S2 exposure-feedback links. The full-corpus size
 # rejection remains a product limitation, not a passed production check.
 s2run=json.loads((E/'04_live_s2/ORIGINAL_RUN_SUMMARY.json').read_text())['run_id']
 removed=r.query('MATCH(s)-[k:OBSERVED_OUTCOME]->(ev:Evidence)-[:VERIFIES]->(o:VerifiedOutcome {run_id:$run}) RETURN s.id,k.id,k.payload_json,ev.id',{'run':s2run})
 write(out/'EXPLICIT_CONTROL_CORPUS_SUBSET.json',{'scope':'COPY_ONLY; exclude later S2 OBSERVED_OUTCOME links for bounded three-state/authority control','removed_links':removed,'no_live_or_historical_truth_change':True,'production_size_failure_remains':'governance/d_mcp.jsonl: MESSAGE_SIZE_LIMIT','production_capacity_status':'FAIL_UNFIXED'})
 for row in removed:r.query('MATCH()-[k:OBSERVED_OUTCOME {id:$id}]->() DELETE k',{'id':row[1]},read_only=False)
 write(out/'graph_before.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 contexts={ep:public_runtime_context(json.loads((E/'owned_runtime/source/benchmark/scenarios'/ep/'public.json').read_text())) for ep in ['A','D']}
 with wire('d',contexts['D']) as (c,b):
  q=resolve(c);write(out/'d_actual_query.json',q)
  for label,i,want in [('atomic_apply',ATOMIC_ID,'APPLY'),('new_bounded_apply',eid,'APPLY'),('real_mcp_negative_transfer_rlock',LOCK_ID,'ABSTAIN')]:check(label,byid(q,i)['decision']==want,byid(q,i))
  bundle=c.tool('build_evidence_bundle',{'experience_id':LOCK_ID,'query_id':q['query_id']});check('negative_transfer_actual_counterexample',not bundle['result'].get('isError') and 'counterexample' in json.dumps(bundle['result']).lower(),bundle)
  before=r.state_fingerprint();bad=RPCClient(b,'invalid-scoped-capability',out/'wrong_auth_client.jsonl');check('wrong_scoped_auth_refused',bad.ack.get('aevora_transport')=='REJECTED',bad.ack);bad.close();check('wrong_auth_no_graph_write',r.state_fingerprint()==before,r.state_fingerprint())
  s1=json.loads((E/'02_live_s1/NATIVE_LIFECYCLE_RESULT.json').read_text());foreign=s1['proposals'][0]['arguments']['proposal'];foreign_query=foreign['source_references'][0]['id']
  noauthority('foreign_query_denied',c,'build_evidence_bundle',{'experience_id':eid,'query_id':foreign_query})
  noauthority('forged_verified_outcome_denied',c,'record_decision',{'decision':{'query_id':q['query_id'],'experience_id':eid,'decision':'APPLY','reason':'Trusted control tests forbidden authority fields','verified':True}})
  noauthority('foreign_proposal_provenance_denied',c,'propose_experience',{'proposal':dict(foreign,candidate_key='foreign-provenance-control')})
  noauthority('authority_in_proposal_denied',c,'propose_experience',{'proposal':dict(foreign,authority='TRUSTED_HOST')})
 for label,tool in [('publication','publish_experience'),('review','review_candidate')]:
  with wire('forbidden_'+label,contexts['D']) as (c,b):
   before=r.state_fingerprint();reply=c.tool(tool,{'candidate_id':'untrusted-control'})
   check('public_'+label+'_transport_denial',reply is None and b.metadata['rejections'].get('TOOL_NOT_ALLOWED')==1 and r.state_fingerprint()==before,{'response':reply,'rejections':b.metadata['rejections'],'expected':'Forbidden tool closes channel at broker allowlist, before SDK dispatch'})
 with wire('unknown',{}) as (c,b):
  q=resolve(c);write(out/'unknown_actual_query.json',q)
  check('unknown_facts_verify_not_default_true',all(byid(q,i)['decision']=='VERIFY' for i in [ATOMIC_ID,LOCK_ID,eid]),{i:byid(q,i) for i in [ATOMIC_ID,LOCK_ID,eid]})
  check('unknown_why_lists_missing_premises',bool(byid(q,eid)['unknown_premises']),byid(q,eid)['unknown_premises'])
 with wire('a',contexts['A']) as (c,b):
  q=resolve(c);write(out/'a_actual_query.json',q);check('rlock_threaded_support_positive',byid(q,LOCK_ID)['decision']=='APPLY',byid(q,LOCK_ID));check('new_experience_does_not_broaden_to_a',byid(q,eid)['decision']=='ABSTAIN',byid(q,eid))
 # Real edge removal/restoration on the COPY, never change live task history.
 baseline=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'edge_before.json',baseline)
 row=r.query('MATCH(e:Experience {id:$id})-[:HAS_REVISION]->(:ExperienceRevision)-[:USES_RULE]->(x:Rule)-[k:REQUIRES]->(p:Premise) RETURN x.id,p.id,k.id,k.payload_json,k.payload_sha256 ORDER BY k.id LIMIT 1',{'id':eid})[0]
 rid,pid,kid,payload,h=row;write(out/'removed_edge.json',{'source':rid,'target':pid,'edge_id':kid,'payload':json.loads(payload),'sha256':h})
 try:
  r.query('MATCH()-[k:REQUIRES {id:$id}]->() DELETE k',{'id':kid},read_only=False)
  with wire('edge_cut',contexts['D']) as (c,b):
   q=resolve(c);write(out/'edge_cut_query.json',q);check('missing_edge_changes_why_and_refuses_apply',byid(q,eid)['decision']=='VERIFY' and bool(byid(q,eid)['graph_integrity_issues']),byid(q,eid))
 finally:r.put_edge('REQUIRES','Rule',rid,'Premise',pid,json.loads(payload))
 restored=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'edge_restored.json',restored)
 # Authorized queries add telemetry: compare original edge bytes and truth paths,
 # not whole-graph identity after real resolve operations.
 original_edges={x[2]:x for x in baseline['edges']};new_edges={x[2]:x for x in restored['edges']}
 check('edge_exact_bytes_restored',original_edges[kid]==new_edges[kid],{'before':original_edges[kid],'after':new_edges[kid]})
 check('all_original_edges_unchanged',all(new_edges.get(i)==v for i,v in original_edges.items()),{'original_edge_count':len(original_edges),'new_edge_count':len(new_edges)})
 with wire('edge_recovered',contexts['D']) as (c,b):
  q=resolve(c);check('edge_restore_recovers_apply',byid(q,eid)['decision']=='APPLY',byid(q,eid))
 # Strict source authority refuses wrong manifest before outcome ingestion.
 run=E/'02_live_s1/runs'/s1['run_id'];cid=s1['proposals'][0]['result']['candidate_id'];before=r.state_fingerprint()
 anchor=TrustAnchor(run,'0'*64,{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=E/'source',source_manifest_sha256=sha(E/'source/SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
 try:verify_orderflow_candidate(r,cid,anchor,'evaluation_report.json');raise AssertionError('forged pin accepted')
 except ValueError as error:check('forged_source_pin_denied',r.state_fingerprint()==before,{'error_type':type(error).__name__,'reason':str(error)})
 live_unchanged=main.state_fingerprint()==original;check('live_graph_truth_and_telemetry_untouched',live_unchanged,main.state_fingerprint())
 write(out/'graph_after.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION));r._client.connection.save()
 write(out/'RESULT.json',{'status':'PASS','checks':checks,'model_requests':0,'actor':'TRUSTED_HOST_REAL_MCP_GRAPH_CONTROL','graph_copy':name,'live_graph_unchanged':live_unchanged,'causal_benefit':'UNKNOWN','at':now()})
 print('C4_REAL_GOVERNANCE_CONTROLS',len(checks),'PASS')
finally:raw.close();r.close();main.close()
