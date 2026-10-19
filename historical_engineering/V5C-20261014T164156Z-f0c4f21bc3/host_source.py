"""Trusted source gate: reuse strict native/Oracle verifier, never repair a candidate."""
from pathlib import Path
import sys,json,datetime
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.admission import verify_orderflow_candidate
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from scripts.aevora_h2_graph_e2e import RawCommands
out=E/'03_feedback/source';out.mkdir()
s=json.loads((E/'02_live_s1/ORIGINAL_RUN_SUMMARY.json').read_text());run=E/'02_live_s1/runs'/s['run_id']
manifest=json.loads((run/'run_evidence_manifest.json').read_text())
for n,h in manifest['files'].items():assert sha(run/n)==h
write(out/'EXISTING_RUN_SEAL_CHECK.json',{'status':'PASS','run_id':run.name,'sealed_file_count':len(manifest['files']),'seal_sha256':sha(run/'run_evidence_manifest.json'),'original_launcher_exit':1,'launcher_failure':'POST_RUN_DUPLICATE_SEAL_FILE_EXISTS; Runner already sealed completed PASS','no_reexecution_or_seal_rewrite':True})
anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=E/'source',source_manifest_sha256=sha(E/'source/SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);life=CandidateLifecycle(r)
try:
 write(out/'graph_before.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION))
 verified=verify_outcome(anchor,'evaluation_report.json');write(out/'verified_outcome_receipt.json',verified)
 ids=[x[0] for x in r.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id ORDER BY c.id',{'run':run.name})]
 assert ids,'No native candidate; positive closure not achieved'
 grant=ReviewGrant('v5c-trusted-source-reviewer',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).isoformat())
 results=[]
 for i,cid in enumerate(ids):
  d=out/str(i);d.mkdir();v=life.inspect(cid);write(d/'untrusted_candidate.json',v)
  life.transition(cid,'EVIDENCE_PENDING',expected_head_sha256=v['head_sha256'],event_key='v5c-open',reason='Actual Agent proposal requires pinned same-run native patch and independent Oracle verification',grant=grant)
  try:
   result=verify_orderflow_candidate(r,cid,anchor,'evaluation_report.json');write(d/'source_verification.json',result)
   results.append({'candidate_id':cid,'verified':True,'body_sha256':v['candidate']['body_sha256'],'submission_sha256':result['source']['submission_sha256'],'source_id':result['source']['id'],'outcome_verdict':result['outcome_verdict'],'semantic_review':'PENDING; no publication yet'})
  except Exception as error:
   results.append({'candidate_id':cid,'verified':False,'error_type':type(error).__name__,'reason':str(error)});write(d/'source_rejection.json',results[-1])
 write(out/'graph_after.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION));r._client.connection.save()
 write(out/'RESULT.json',{'status':'PASS' if all(x['verified'] for x in results) else 'FAIL','run_id':run.name,'candidates':results,'source_epoch_label_limitation':'Existing verifier retains historical H3_NEW_NATIVE_SESSION label; actual V5C commit/tree/run hashes separately pinned','at':now(),'causal_benefit':'UNKNOWN'})
 print('HOST_SOURCE',verified['verdict'],len(results),all(x['verified'] for x in results))
 assert all(x['verified'] for x in results)
finally:raw.close();r.close()
