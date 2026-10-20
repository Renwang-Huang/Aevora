"""Fresh real graph control. Historical verified source explicitly not new Agent."""
from pathlib import Path
import os,sys,json,datetime,uuid
E=Path(__file__).resolve().parent;sys.path.insert(0,str(E));from audit import write,sha,now,C
sys.path.insert(0,str(E/'owned_runtime/source'))
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.historical_import import import_verified_history,public_context,LOCK_ID,ATOMIC_ID
from aevora.experience_resolver import ExperienceResolver
from aevora.mcp_server import ExperienceService
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION,digest,ImmutableConflict,InvalidRecord
from scripts.aevora_h2_graph_e2e import RawCommands
out=E/'04_falkordb/graph_controls-attempt3';out.mkdir(mode=0o700)
os.environ['AEVORA_FALKORDB_GRAPH']='aevora_pregen2_controls_'+uuid.uuid4().hex
repo=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(repo);life=CandidateLifecycle(repo);checks=[]
def check(name,condition,data):
 write(out/(name+'.json'),data);checks.append({'name':name,'status':'PASS' if condition else 'FAIL','at':now(),'path':str(out/(name+'.json'))})
 if not condition:raise ValueError('Control failed: '+name)
def resolve(context):return ExperienceResolver(repo).resolve(context,persist_snapshots=False)
def selected(r,eid):return next(x for x in r['candidates'] if x['experience_id']==eid)
grant=ReviewGrant('pregen2-trusted-host-control',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).isoformat())
def move(cid,state,key,metadata=None):return life.transition(cid,state,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key=key,reason='This round trusted Host control, not model execution',grant=grant,metadata=metadata)
try:
 init=life.initialize();empty=resolve(public_context('single_process_multi_thread'));check('empty_live_available',empty['status']=='AVAILABLE' and empty['candidates']==[],{'schema':init,'resolution':empty})
 p=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/orderflow_incident_lab/m1_validation');a=Path((p/'CURRENT').read_text().strip());a=a if a.is_absolute() else p/a
 imported=import_verified_history(repo,a);fingerprint=repo.state_fingerprint();again=import_verified_history(repo,a)
 check('actual_historical_import_idempotent',fingerprint==repo.state_fingerprint(),{'initial':imported,'repeat':again,'origin':'FOUR_HISTORICAL_VERIFIED_OUTCOMES; NOT_NEW_AGENT'})
 contexts={'APPLY':public_context('single_process_multi_thread'),'VERIFY':public_context(None),'ABSTAIN':public_context('multi_process_shared_sqlite')}
 rows={k:resolve(v) for k,v in contexts.items()}
 check('real_three_state_rlock_transfer',all(selected(rows[k],LOCK_ID)['decision']==k for k in contexts),rows)
 before=resolve(contexts['ABSTAIN']);x=selected(before,ATOMIC_ID);path=x['principle_support_paths'][0];s=path['records']['Evidence']['id'];t=path['records']['VerifiedOutcome']['id']
 edges=repo.query('MATCH(s:Evidence {id:$s})-[r:VERIFIES]->(t:VerifiedOutcome {id:$t}) RETURN r.id,r.payload_json',{'s':s,'t':t});assert len(edges)==1
 b=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'EDGE_BEFORE.json',b)
 repo.query('MATCH(s:Evidence {id:$s})-[r:VERIFIES {id:$id}]->(t:VerifiedOutcome {id:$t}) DELETE r',{'s':s,'t':t,'id':edges[0][0]},read_only=False)
 ab=resolve(contexts['ABSTAIN']);abg=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION)
 check('actual_single_edge_cut_changes_why',b['nodes']==abg['nodes'] and len(abg['edges'])==len(b['edges'])-1 and selected(ab,ATOMIC_ID)['retrieval_snapshot_sha256']!=x['retrieval_snapshot_sha256'],{'before':before,'after':ab,'edge':edges[0],'graph_after':abg})
 repo.put_edge('VERIFIES','Evidence',s,'VerifiedOutcome',t,json.loads(edges[0][1]));restored=resolve(contexts['ABSTAIN'])
 check('edge_restore_exact_graph',capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION)==b and selected(restored,ATOMIC_ID)['retrieval_snapshot_sha256']==x['retrieval_snapshot_sha256'],restored)
 outcome=repo.get_node('VerifiedOutcome',path['records']['VerifiedOutcome']['id']);run=outcome['run_id'];facts=path['records']['Context']['facts']
 proposal={'candidate_key':'pregen2-host-history-control','title':'Explicit Host review of recorded SQLite principle','strategy':'sqlite_conditional_update_in_transaction','public_summary':'Host-owned lifecycle control from an independently verified historical source; this is not a new model discovery.','necessary_conditions':{'shared_state_kind':['sqlite_file'],'transaction_guarantees':['sqlite_atomic_write_transactions']},'inapplicable_conditions':{},'scope':{'concurrency_scope':['independent_processes']},'unknown_fields':[],'limitations':['Historical applicability control only; causal benefit UNKNOWN'],'source_references':[]}
 cid=life.propose(run,proposal)['candidate_id'];proposed=life.inspect(cid);assert life.propose(run,proposal)['candidate_id']==cid
 check('untrusted_candidate_not_published',proposed['head']['state']=='PROPOSED' and repo.query('MATCH(c:Candidate {id:$id}) RETURN count(c)',{'id':cid})==[[1]],proposed)
 move(cid,'EVIDENCE_PENDING','host-pending');source={'id':'source-verification:pregen2-history-control','candidate_id':cid,'run_id':run,'authority':'TRUSTED_HOST_SOURCE_VERIFIER','origin':'maintainer_seed','source_sha256':outcome['source_manifest_sha256'],'submission_sha256':outcome['submission_digest'],'outcome_id':outcome['id'],'facts':facts,'review_scope':'CURRENT_HOST_CONTROL_OF_VERIFIED_HISTORY_NOT_LIVE_AGENT'}
 repo.put_node('SourceVerification',source);repo.put_edge('HAS_SOURCE_VERIFICATION','Candidate',cid,'SourceVerification',source['id'])
 move(cid,'ADMITTED_BOUNDED','host-admit',{'source_id':source['id'],'scope':proposal['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'})
 published=life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='host-publish',reason='Fresh bounded lifecycle control from verified historical source',grant=grant)
 svc=ExperienceService(run_id='pregen2-controlled-reader',public_context=facts,repository=repo);q=svc.resolve_experience({});bundle=svc.build_evidence_bundle(published['experience_id'],q['query_id'])
 check('fresh_host_publication_resolved',selected(q,published['experience_id'])['decision']=='APPLY',{'view':life.inspect(cid),'published':published,'query':q,'bundle':bundle})
 move(cid,'WITHDRAWN','host-withdraw');withdrawn=svc.resolve_experience({});replay=svc.build_evidence_bundle(published['experience_id'],q['query_id'])
 check('withdrawal_future_exclusion_snapshot_retained',published['experience_id'] not in [x['experience_id'] for x in withdrawn['candidates']] and replay==bundle,{'current':withdrawn,'historical_snapshot':replay,'view':life.inspect(cid)})
 def denied(name,fn,condition):
  counts=repo.query('MATCH(n:VerifiedOutcome) RETURN count(n)')[0][0]
  try:fn()
  except (InvalidRecord,ImmutableConflict,ValueError) as e:check(name,condition() and counts==repo.query('MATCH(n:VerifiedOutcome) RETURN count(n)')[0][0],{'error_type':type(e).__name__,'verified_outcomes_unchanged':counts,'state_fingerprint':repo.state_fingerprint()})
  else:check(name,False,{'unexpected_acceptance':True})
 for field,value in [('verified',True),('outcome','PASS'),('run_id','foreign'),('source_type','natural_agent_run')]:denied('reject_forged_'+field,lambda field=field,value=value:life.propose(run,{**proposal,field:value}),lambda:True)
 bad={**proposal,'candidate_key':'missing-proof','source_references':[]};badid=life.propose('pregen2-negative-control',bad)['candidate_id'];move(badid,'EVIDENCE_PENDING','pending')
 denied('missing_oracle_source_cannot_admit',lambda:move(badid,'ADMITTED_BOUNDED','forge',{'source_id':'source:invented-run','scope':proposal['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'}),lambda:life.inspect(badid)['head']['state']=='EVIDENCE_PENDING')
 move(badid,'REJECTED','host-reject')
 denied('withdrawn_head_cannot_republish',lambda:life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='replay',reason='Negative control',grant=grant),lambda:life.inspect(cid)['head']['state']=='WITHDRAWN')
 snapshot=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'FINAL_GRAPH.json',snapshot);saved=repo._client.connection.save();check('owned_save_success',saved is True,{'save_response':saved,'graph':repo.graph_name,'port':17705})
 write(out/'RESULT.json',{'status':'PASS','at':now(),'checks':checks,'graph':repo.graph_name,'schema_version':LIFECYCLE_SCHEMA_VERSION,'classification':'TRUSTED_HOST_GRAPH_CONTROL; authentic historical source + new graph operations; NOT_NEW_AGENT','new_verified_outcomes':0,'causal_benefit':'UNKNOWN','graph_snapshot_sha256':sha(out/'FINAL_GRAPH.json')})
 print('V3 graph controls PASS',len(checks),repo.graph_name)
finally:raw.close();repo.close()
