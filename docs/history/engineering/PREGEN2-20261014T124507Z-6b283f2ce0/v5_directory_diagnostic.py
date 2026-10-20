from pathlib import Path
import sys,json
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from benchmark.runner import BenchmarkRunner
from integrations.runtime_evidence import seal_run
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
orig=json.loads((E/'06_live_agent/s1/REPORT_SUMMARY.json').read_text());source_run=E/'06_live_agent/s1/runs'/orig['run_id'];out=E/'06_live_agent/postmortem_workspace';out.mkdir(mode=0o700)
# An independent check of the existing workspace submission evidence protocol;
# same untouched source. This is additional Host verification, not another Agent.
report=BenchmarkRunner(out/'oracle_runs').evaluate('D',source_run/'participant',variant='v01');run=out/'oracle_runs'/report['run_id'];seal_run(run)
src=E/'06_live_agent/source';anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=src,source_manifest_sha256=sha(src/'SOURCE_TRUST_MANIFEST.json'),source_manifest_relative_path='SOURCE_TRUST_MANIFEST.json')
try:
 verified=verify_outcome(anchor,'evaluation_report.json');write(out/'STRICT_VERIFIED_OUTCOME.json',verified);status='PASS_TRUSTED_DIAGNOSTIC'
except Exception as e:write(out/'STRICT_REJECTION.json',{'error_type':type(e).__name__,'reason':str(e),'at':now()});status='REJECTED_BY_TRUSTED_VERIFIER'
write(out/'RESULT.json',{'status':status,'source_actor_run_id':source_run.name,'source_actor_runtime_status':'ERROR','source_actor_original_evaluation':'NOT_RUN','diagnostic_run_id':run.name,'diagnostic_outcome':report['overall_status'],'evaluated_tree_sha256':report.get('submission',{}).get('evaluated_sha256'),'kind':'ADDITIONAL_HOST_WORKSPACE_SUBMISSION_VERIFICATION_OF_IDENTICAL_ARTIFACT','new_agent_session':False,'manual_repair':False,'original_score_upgraded':False,'at':now()})
print('Diagnostic workspace source',status,report['overall_status'],run.name)
