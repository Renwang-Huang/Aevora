"""Honest Host-controlled publication, never labeled Agent-originated discovery."""
from pathlib import Path
import sys,json,os,datetime
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.feedback import ingest_outcome,_environment
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from scripts.aevora_h2_graph_e2e import RawCommands
protocol=json.loads((E/'06_live_agent/challenge_protocol_frozen.json').read_text());os.environ['AEVORA_FALKORDB_GRAPH']=protocol['graph'];out=E/'06_live_agent/host_controlled_feedback';out.mkdir(mode=0o700)
original=json.loads((E/'06_live_agent/s1/REPORT_SUMMARY.json').read_text());s1=E/'06_live_agent/s1/runs'/original['run_id'];d=json.loads((E/'06_live_agent/postmortem_workspace/RESULT.json').read_text());diag=E/'06_live_agent/postmortem_workspace/oracle_runs'/d['diagnostic_run_id'];src=E/'06_live_agent/source'
def anchor(run):return TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=src,source_manifest_sha256=sha(src/'SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);life=CandidateLifecycle(r)
try:
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'BEFORE.json',before)
 assert r.query('MATCH(c:Candidate {run_id:$run}) RETURN count(c)',{'run':s1.name})==[[0]]
 try:verify_outcome(anchor(s1),'evaluation_report.json')
 except Exception as e:write(out/'ORIGINAL_S1_CORRECTLY_REJECTED.json',{'at':now(),'error_type':type(e).__name__,'reason':str(e),'source_run_id':s1.name,'native_runtime':'ERROR','original_evaluation':'NOT_RUN','no_original_verified_outcome':True})
 else:raise ValueError('Incomplete original S1 must not be promoted')
 verified=verify_outcome(anchor(diag),'evaluation_report.json');assert verified['verdict']=='PASS'
 report=json.loads((diag/'evaluation_report.json').read_text());patch=json.loads((E/'06_live_agent/postmortem/RESULT.json').read_text());assert report['submission']['evaluated_sha256']==patch['evaluated_tree_sha256']
 feedback=ingest_outcome(r,anchor(diag),'evaluation_report.json');write(out/'REAL_DIAGNOSTIC_OUTCOME_INGESTION.json',feedback)
 context,task=_environment(report,None);facts=context['facts']
 body={'candidate_key':'host-stopped-artifact-control','title':'Host-controlled evidence for a budget-stopped code artifact','strategy':'conditional_relative_sql_update_in_one_write_transaction','public_summary':'An actual new Codex session edited the code but failed its runtime request budget before formal submission. The unchanged stopped artifact separately passed an independent Host evaluation. This proposal and publication are Host-controlled, not a native Agent proposal or a completed automatic Agent run.','necessary_conditions':{'shared_state_kind':['sqlite_file'],'transaction_guarantees':['sqlite_atomic_write_transactions']},'inapplicable_conditions':{},'scope':{'concurrency_scope':['independent_processes']},'unknown_fields':[],'limitations':['Original Agent run remains ERROR and its evaluation remains NOT_RUN.','Independent postmortem repair evidence is bounded to the evaluated API and topology.','Causal benefit UNKNOWN; no Agent-originated proposal lifecycle is certified.'],'source_references':[]}
 cid=life.propose(diag.name,body)['candidate_id'];g=ReviewGrant('pregen2-trusted-host-controller',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=20)).isoformat())
 def move(state,key,metadata=None):return life.transition(cid,state,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key=key,reason='Explicit Host-controlled source/semantic review; original natural run remains failed',grant=g,metadata=metadata)
 move('EVIDENCE_PENDING','pending')
 source={'id':'source-verification:pregen2-host-control','candidate_id':cid,'run_id':diag.name,'authority':'TRUSTED_HOST_SOURCE_VERIFIER','origin':'maintainer_seed','source_epoch':'PREGEN2_HOST_CONTROLLED_POSTMORTEM','source_sha256':sha(diag/'run_evidence_manifest.json'),'submission_sha256':patch['submission_sha256'],'outcome_id':verified['id'],'facts':facts,'actor_source_run_id':s1.name,'actor_source_runtime_status':'ERROR','actor_proposed_candidate':False,'independent_diagnostic_tree_sha256':report['submission']['evaluated_sha256']}
 r.put_node('SourceVerification',source);r.put_edge('HAS_SOURCE_VERIFICATION','Candidate',cid,'SourceVerification',source['id']);write(out/'SOURCE_VERIFICATION_HOST_CONTROL.json',source)
 write(out/'SEMANTIC_REVIEW.json',{'at':now(),'principal':g.principal,'actual_patch_sha256':patch['submission_sha256'],'observed_diff':'inventory.reserve always uses capacity-conditioned relative UPDATE and rowcount insufficiency; create_order no longer carries pretransaction stock snapshot; existing write transaction still spans order/inventory/ledger','independent_tests':28,'review':'Bounded plausible in independently tested shared SQLite/multiprocess scope','candidate_origin':'HOST_CONTROLLED_MAINTAINER_SEED; NOT_AGENT_PROPOSAL','source_bytes_changed_by_host':False,'original_runtime_grade_upgraded':False})
 move('ADMITTED_BOUNDED','admit',{'source_id':source['id'],'scope':body['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'});pub=life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='publish',reason='Host-controlled bounded publication from real independent diagnostic; not completed natural runtime',grant=g)
 write(out/'PUBLICATION.json',pub);after=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'AFTER.json',after);r._client.connection.save()
 write(out/'RESULT.json',{'status':'PASS_HOST_CONTROLLED_BRANCH_ONLY','source_actor_run_id':s1.name,'original_s1_verified_outcome':'NOT_CREATED','diagnostic_run_id':diag.name,'diagnostic_verified_outcome':verified['id'],'candidate_origin':'HOST_CONTROLLED','agent_originated_lifecycle':'UNVERIFIED_NOT_PROPOSED','published_experience_id':pub['experience_id'],'candidate_id':cid,'source_before_sha256':sha(out/'BEFORE.json'),'source_after_sha256':sha(out/'AFTER.json'),'original_s1_runtime':'ERROR','original_s1_evaluation':'NOT_RUN','at':now(),'causal_benefit':'UNKNOWN'})
 print('Host controlled feedback published',pub['experience_id'])
finally:raw.close();r.close()
