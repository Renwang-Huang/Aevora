"""Existing strict Host outcome/source gate; no business edits or Agent substitutes."""
from pathlib import Path
import sys,json,datetime
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.admission import verify_orderflow_candidate
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.feedback import ingest_outcome
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from scripts.aevora_h2_graph_e2e import RawCommands
phase=sys.argv[1];assert phase in {'S1','S2'};out=E/'04_live'/phase/'host_source';out.mkdir()
s=json.loads((E/'04_live'/phase/'ORIGINAL_RUN_SUMMARY.json').read_text());run=E/'04_live'/phase/'runs'/s['run_id']
manifest=json.loads((run/'run_evidence_manifest.json').read_text())
for n,h in manifest['files'].items():assert sha(run/n)==h
write(out/'ORIGINAL_RUN_SEAL_CHECK.json',{'status':'PASS','run_id':run.name,'file_count':len(manifest['files']),'manifest_sha256':sha(run/'run_evidence_manifest.json'),'no_run_modification':True})
anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=E/'source',source_manifest_sha256=sha(E/'source/SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
r=GraphRepository.from_environment();expected=json.loads((E/'04_live/INITIAL_GRAPH.json').read_text())['graph'];assert r.graph_name==expected
raw=RawCommands(out);raw.attach(r);life=CandidateLifecycle(r)
try:
 write(out/'graph_before.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 verified=verify_outcome(anchor,'evaluation_report.json');write(out/'verified_outcome_receipt.json',verified)
 feedback=ingest_outcome(r,anchor,'evaluation_report.json');write(out/'trusted_feedback.json',feedback)
 ids=[row[0] for row in r.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id ORDER BY c.id',{'run':run.name})]
 grant=ReviewGrant('v5c1-trusted-source-verifier',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).isoformat());results=[]
 for index,cid in enumerate(ids):
  d=out/str(index);d.mkdir();view=life.inspect(cid);write(d/'untrusted_candidate.json',view)
  if view['head']['state']=='PROPOSED':
   life.transition(cid,'EVIDENCE_PENDING',expected_head_sha256=view['head_sha256'],event_key='v5c1-source-open',reason='Actual native proposal requires independent source and outcome verification before any publication',grant=grant)
  try:
   source=verify_orderflow_candidate(r,cid,anchor,'evaluation_report.json');write(d/'source_verification.json',source)
   results.append({'candidate_id':cid,'verified':True,'body_sha256':view['candidate']['body_sha256'],'submission_sha256':source['source']['submission_sha256'],'source_id':source['source']['id'],'outcome_verdict':source['outcome_verdict'],'semantic_review':'PENDING_NOT_PUBLICATION'})
  except Exception as error:
   rejection={'candidate_id':cid,'verified':False,'error_type':type(error).__name__,'reason':str(error)};write(d/'source_rejection.json',rejection);results.append(rejection)
 write(out/'graph_after.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION));r._client.connection.save()
 write(out/'RESULT.json',{'at':now(),'status':'PASS_TRUSTED_OUTCOME_AND_FEEDBACK','phase':phase,'run_id':run.name,'independent_verdict':verified['verdict'],'test_count':verified['test_count'],'native_candidate_count':len(ids),'candidate_source_results':results,'agent_proposal_status':'NATIVE_PROPOSAL_OBSERVED' if ids else 'PROPOSAL_NOT_ACHIEVED','host_publication':'NOT_PERFORMED_BY_SOURCE_GATE','source_epoch_label_limitation':'Existing verifier historical label retained; actual V5C1 source/run hashes pinned separately','observed_feedback_interpretation':'FULL_QUERY_CANDIDACY; not proof of wire delivery, explicit adoption or causal benefit','causal_benefit':'UNKNOWN'})
 print('HOST_VERIFIED_OUTCOME_FEEDBACK',phase,verified['verdict'],verified['test_count'],'native_candidates',len(ids),flush=True)
finally:raw.close();r.close()
