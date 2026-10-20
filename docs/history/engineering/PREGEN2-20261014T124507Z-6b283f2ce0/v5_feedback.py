"""Host verifies untouched native source; no candidate body/patch is repaired."""
from pathlib import Path
import sys,json,os,datetime
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.admission import verify_orderflow_candidate
from aevora.feedback import ingest_outcome
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from scripts.aevora_h2_graph_e2e import RawCommands
protocol=json.loads((E/'06_live_agent/challenge_protocol_frozen.json').read_text());os.environ['AEVORA_FALKORDB_GRAPH']=protocol['graph']
summary=json.loads((E/'06_live_agent/s1/REPORT_SUMMARY.json').read_text());run=E/'06_live_agent/s1/runs'/summary['run_id'];source=E/'06_live_agent/source'
out=E/'06_live_agent/host_feedback';out.mkdir(mode=0o700);r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);life=CandidateLifecycle(r)
anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=source,source_manifest_sha256=sha(source/'SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
grant=ReviewGrant('pregen2-trusted-host-review',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).isoformat())
def move(cid,state,key,reason,metadata=None):return life.transition(cid,state,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key=key,reason=reason,grant=grant,metadata=metadata)
try:
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'BEFORE.json',before)
 ids=[x[0] for x in r.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id ORDER BY c.id',{'run':run.name})];rows=[]
 try:
  verified=verify_outcome(anchor,'evaluation_report.json');write(out/'STRICT_VERIFIED_OUTCOME.json',verified)
  feedback=ingest_outcome(r,anchor,'evaluation_report.json');write(out/'TRUSTED_FEEDBACK.json',feedback)
 except Exception as e:
  verified=None;feedback=None;write(out/'TRUSTED_SOURCE_REJECTION.json',{'at':now(),'error_type':type(e).__name__,'reason':str(e),'source_report_sha256':sha(run/'evaluation_report.json'),'no_outcome_fabricated':True})
 approval=json.loads((E/'06_live_agent/HOST_SEMANTIC_REVIEW.json').read_text()) if (E/'06_live_agent/HOST_SEMANTIC_REVIEW.json').exists() else {}
 for i,cid in enumerate(ids):
  d=out/str(i);d.mkdir(mode=0o700);view=life.inspect(cid);write(d/'BEFORE.json',view)
  move(cid,'EVIDENCE_PENDING','host-open','Actual untrusted proposal requires independently pinned native/patch/Oracle source')
  row={'candidate_id':cid,'run_id':run.name,'proposal_body_sha256':view['candidate']['body_sha256'],'at':now()}
  try:
   s=verify_orderflow_candidate(r,cid,anchor,'evaluation_report.json');write(d/'SOURCE_VERIFICATION.json',s)
   if not verified or verified['verdict']!='PASS':raise ValueError('Independent source not PASS; no bounded support publication')
   if approval.get('candidate_id')!=cid or approval.get('body_sha256')!=view['candidate']['body_sha256'] or approval.get('submission_sha256')!=s['source']['submission_sha256'] or approval.get('semantic_review')!='BOUNDED_PLAUSIBLE_FROM_ACTUAL_PATCH':raise ValueError('No actual Host patch/body semantic approval receipt')
   move(cid,'ADMITTED_BOUNDED','host-admit','Independently passed current source; bounded factual applicability only, causal benefit UNKNOWN',{'source_id':s['source']['id'],'scope':view['candidate']['body']['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'})
   pub=life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='host-publish',reason='Host confirms one actual tested repair in its declared scope; no universal guarantee',grant=grant);write(d/'PUBLICATION.json',pub);row.update(state='PUBLISHED',experience_id=pub['experience_id'])
  except Exception as e:
   row.update(state=life.inspect(cid)['head']['state'],error_type=type(e).__name__,reason=str(e),review='NOT_ADMITTED; original proposal/body/patch unchanged')
   if verified is None or verified['verdict']!='PASS':move(cid,'REJECTED','host-reject','No valid completed independent PASS native source; preserve original failure without publication');row['state']='REJECTED'
   write(d/'REJECTION_OR_PENDING.json',row)
  write(d/'AFTER.json',life.inspect(cid));rows.append(row)
 after=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'AFTER.json',after);r._client.connection.save()
 write(out/'RESULT.json',{'status':'PASS_TRUSTED_FEEDBACK_AND_PUBLICATION' if feedback and any(x['state']=='PUBLISHED' for x in rows) else 'PARTIAL_OR_CORRECT_REJECTION','run_id':run.name,'candidate_count':len(rows),'candidates':rows,'new_model_source':True,'strict_outcome_verdict':verified['verdict'] if verified else 'UNVERIFIED','feedback_accepted':feedback is not None,'graph_changed':before!=after,'graph_before_sha256':sha(out/'BEFORE.json'),'graph_after_sha256':sha(out/'AFTER.json'),'at':now(),'causal_benefit':'UNKNOWN'})
 print('Host feedback',json.dumps({'candidate_count':len(rows),'states':[x['state'] for x in rows],'outcome':verified['verdict'] if verified else 'UNVERIFIED'}))
finally:raw.close();r.close()
