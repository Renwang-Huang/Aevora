"""Full genuine post-S2 graph COPY: dependency, withdrawal, conflict and trust controls."""
from pathlib import Path
import os,sys,json,uuid,tempfile,secrets,datetime
from contextlib import contextmanager
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.checkpoint import capture_graph
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.mcp_broker import MCPBroker
from integrations.aevora import public_runtime_context
from scripts.aevora_h2_security import RPCClient
from scripts.aevora_h2_graph_e2e import RawCommands
out=E/'05_graph/post_feedback_controls_retry1';out.mkdir();main=GraphRepository.from_environment();original=main.state_fingerprint();name='aevora_v5c1_postcontrol_'+uuid.uuid4().hex;main._graph.copy(name);os.environ['AEVORA_FALKORDB_GRAPH']=name;r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);eid=json.loads((E/'04_live/PUBLISHED_EXPERIENCE.json').read_text())['new_published_experience_id'];facts=public_runtime_context(json.loads((E/'owned_runtime/source/benchmark/scenarios/D-V02/public.json').read_text()));checks=[]
def check(label,ok,value):
 row={'name':label,'status':'PASS' if ok else 'FAIL','observed':value,'at':now(),'actor':'TRUSTED_HOST_FULL_COPY_CONTROL_NOT_AGENT'};checks.append(row)
 with (out/'checks.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 assert ok,label
@contextmanager
def channel(label):
 with tempfile.TemporaryDirectory(prefix='v5c1-post-') as td:
  token=secrets.token_hex(32);b=MCPBroker(run_id='v5c1-post-'+uuid.uuid4().hex,public_context=facts,socket_path=Path(td)/'mcp.sock',run_token=token,event_path=out/(label+'_mcp.jsonl'),enable_proposals=True)
  with b:
   c=RPCClient(b,token,out/(label+'_client.jsonl'));c.initialize()
   try:yield c
   finally:c.close()
  write(out/(label+'_cleanup.json'),b.metadata)
  check(label+'_owner_revocation_cleanup',b.metadata['token_revoked'] and b.metadata['socket_unlinked'] and b.metadata['handler_cleanup_complete'],b.metadata)
def query(c):
 reply=c.tool('resolve_experience',{'task_context':{}});assert reply and not reply['result'].get('isError');result=reply['result']['structuredContent'];rows=list(result['candidates'])
 while result['has_more']:
  reply=c.tool('resolve_experience',{'task_context':{},'cursor':result['next_cursor']});assert reply and not reply['result'].get('isError');result=reply['result']['structuredContent'];rows+=result['candidates']
 return rows
try:
 write(out/'full_copy_before.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 with channel('baseline') as c:
  rows=query(c);target=next(v for v in rows if v['experience_id']==eid);write(out/'baseline_new_experience.json',target);check('full_post_feedback_new_candidate_present',target['decision']=='VERIFY' and not target['graph_integrity_issues'],target)
 rid,pid,kid,payload,fingerprint=r.query('MATCH(e:Experience {id:$id})-[:HAS_REVISION]->(:ExperienceRevision)-[:USES_RULE]->(x:Rule)-[k:REQUIRES]->(p:Premise) RETURN x.id,p.id,k.id,k.payload_json,k.payload_sha256 ORDER BY k.id LIMIT 1',{'id':eid})[0]
 write(out/'edge_original.json',{'source':rid,'target':pid,'id':kid,'payload':json.loads(payload),'sha256':fingerprint})
 try:
  r.query('MATCH()-[k:REQUIRES {id:$id}]->() DELETE k',{'id':kid},read_only=False)
  with channel('edge_cut') as c:
   broken=next(v for v in query(c) if v['experience_id']==eid);check('missing_required_edge_changes_why_without_false_apply',broken['decision']!='APPLY' and bool(broken['graph_integrity_issues']) and broken['governance_evidence_sha256']!=target['governance_evidence_sha256'],broken)
 finally:r.put_edge('REQUIRES','Rule',rid,'Premise',pid,json.loads(payload))
 edge=r.query('MATCH()-[k:REQUIRES {id:$id}]->() RETURN k.payload_json,k.payload_sha256',{'id':kid})[0];check('edge_exact_bytes_restored',edge==[payload,fingerprint],edge)
 with channel('edge_restored') as c:
  restored=next(v for v in query(c) if v['experience_id']==eid);check('exact_original_provenance_recovers',restored['decision']==target['decision'] and restored['governance_evidence_sha256']==target['governance_evidence_sha256'] and not restored['graph_integrity_issues'],restored)
 # A real graph relation with EXPLICIT SYNTHETIC control records; not an engineering outcome.
 r.attach_evidence(eid,{'id':'evidence:v5c1-post-conflict','source_type':'synthetic_or_test_fixture','source_run_id':'v5c1-post-conflict','public_summary':'EXPLICIT SYNTHETIC GOVERNANCE CONFLICT ON COPY ONLY'},
  {'id':'outcome:v5c1-post-conflict','run_id':'v5c1-post-conflict','submission_digest':'a'*64,'evaluator_fingerprint':'b'*64,'test_suite_fingerprint':'c'*64,'verifier_identity':'SYNTHETIC_POST_GOVERNANCE_CONTROL','verdict':'FAIL'},
  {'id':'context:v5c1-post-conflict','facts':facts},{'id':'task:v5c1-post-conflict','public_title':'Synthetic conflicting evidence control'},relation='COUNTEREXAMPLE')
 with channel('conflict') as c:
  conflict=next(v for v in query(c) if v['experience_id']==eid);check('unknown_material_context_counterexample_stays_potential',conflict['decision']=='VERIFY' and conflict['reason']=='POTENTIALLY_RELEVANT_COUNTEREXAMPLE_NEEDS_CONTEXT' and conflict['evidence_index']['potential_counterexample_paths']['count']==1 and conflict['evidence_index']['relevant_counterexample_paths']['count']==0 and conflict['governance_evidence_sha256']!=target['governance_evidence_sha256'],conflict)
 # Separate fully known legacy D context: require a genuine matching conflict.
 lease_facts=facts;facts=public_runtime_context(json.loads((E/'owned_runtime/source/benchmark/scenarios/D/public.json').read_text()))
 atomic='experience:sqlite-atomic-reservation'
 with channel('known_domain_before_conflict') as c:
  known=next(v for v in query(c) if v['experience_id']==atomic);check('known_domain_positive_before_conflict',known['decision']=='APPLY',known)
 r.attach_evidence(atomic,{'id':'evidence:v5c1-post-known-conflict','source_type':'synthetic_or_test_fixture','source_run_id':'v5c1-post-known-conflict','public_summary':'EXPLICIT SYNTHETIC KNOWN-CONTEXT CONFLICT ON COPY ONLY'},
  {'id':'outcome:v5c1-post-known-conflict','run_id':'v5c1-post-known-conflict','submission_digest':'a'*64,'evaluator_fingerprint':'b'*64,'test_suite_fingerprint':'c'*64,'verifier_identity':'SYNTHETIC_POST_GOVERNANCE_CONTROL','verdict':'FAIL'},
  {'id':'context:v5c1-post-known-conflict','facts':facts},{'id':'task:v5c1-post-known-conflict','public_title':'Synthetic fully known conflict control'},relation='COUNTEREXAMPLE')
 with channel('known_domain_conflict') as c:
  known=next(v for v in query(c) if v['experience_id']==atomic);check('known_domain_conflict_is_relevant_and_changes_apply_to_verify',known['decision']=='VERIFY' and known['reason']=='CONFLICTING_VERIFIED_EVIDENCE' and known['evidence_index']['relevant_counterexample_paths']['count']==1 and known['evidence_index']['evidence_conflicts']['count']>0,known)
 facts=lease_facts
 life=CandidateLifecycle(r);cid=r.get_node('Experience',eid)['publication_candidate_id'];view=life.inspect(cid);grant=ReviewGrant('v5c1-post-control-host',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=20)).isoformat());life.transition(cid,'WITHDRAWN',expected_head_sha256=view['head_sha256'],event_key='v5c1-post-withdraw-copy',reason='Controlled withdrawal on complete post-feedback copy',grant=grant)
 with channel('withdrawn') as c:check('withdrawn_excluded_from_actual_public_retrieval',eid not in [v['experience_id'] for v in query(c)],eid)
 s=json.loads((E/'04_live/S2/ORIGINAL_RUN_SUMMARY.json').read_text());run=E/'04_live/S2/runs'/s['run_id'];before=r.state_fingerprint();anchor=TrustAnchor(run,'0'*64,{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=E/'source',source_manifest_sha256=sha(E/'source/SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
 try:verify_outcome(anchor,'evaluation_report.json');raise AssertionError('forged pin accepted')
 except ValueError as error:check('forged_actual_new_run_host_pin_refused',r.state_fingerprint()==before,{'error_type':type(error).__name__,'reason':str(error)})
 # New authenticated, initialized but empty graph, not an absent-service fallback.
 empty='aevora_v5c1_postempty_'+uuid.uuid4().hex;os.environ['AEVORA_FALKORDB_GRAPH']=empty;emptyrepo=GraphRepository.from_environment();emptyrepo.initialize(schema_version=LIFECYCLE_SCHEMA_VERSION)
 with channel('empty') as c:check('actual_empty_graph_explicit_zero_candidates',query(c)==[],empty)
 emptyrepo.close();os.environ['AEVORA_FALKORDB_GRAPH']=name
 check('same_genuine_live_graph_not_modified_by_controls',main.state_fingerprint()==original,main.state_fingerprint());write(out/'full_copy_after.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 write(out/'RESULT.json',{'status':'PASS','at':now(),'checks':checks,'model_requests':0,'base_graph':main.graph_name,'copy_graph':name,'full_original_nodes':original['node_count'],'full_original_edges':original['edge_count'],'synthetic_conflict_control_only':True,'original_live_graph_unchanged':True});print('POST_FEEDBACK_FULL_COPY_CONTROLS_PASS',len(checks),flush=True)
finally:raw.close();r.close();main.close()
