"""Independent diagnostic of untouched budget-stopped artifact; original Run immutable."""
from pathlib import Path
import sys,json
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from benchmark.participant import extract_submission
from benchmark.runner import BenchmarkRunner
from benchmark.h2_cli import register_h2
from integrations.runtime_evidence import seal_run
register_h2();original=json.loads((E/'06_live_agent/s1/REPORT_SUMMARY.json').read_text());run=E/'06_live_agent/s1/runs'/original['run_id'];seal=sha(run/'run_evidence_manifest.json')
out=E/'06_live_agent/postmortem';out.mkdir(mode=0o700)
meta=extract_submission(run/'workspace',run/'participant',out/'participant_patch.diff');write(out/'HARVEST_RECEIPT.json',{'at':now(),'source_run_id':run.name,'source_runtime':'ERROR','source_evaluation':'NOT_RUN','patch':meta,'scope':'Untouched stopped source; NO_MANUAL_REPAIR; not original automatic submission','original_run_seal_sha256':seal})
r=BenchmarkRunner(out/'oracle_runs').evaluate('D',out/'participant_patch.diff',variant='v01');diag=out/'oracle_runs'/r['run_id'];seal_run(diag)
assert sha(run/'run_evidence_manifest.json')==seal
write(out/'RESULT.json',{'at':now(),'source_run_id':run.name,'diagnostic_run_id':diag.name,'original_status':'ERROR / NOT_RUN / PARTIAL','diagnostic_status':r['overall_status'],'test_results':r.get('test_results'),'submission_sha256':meta['sha256'],'evaluated_tree_sha256':r.get('submission',{}).get('evaluated_sha256'),'no_manual_repair':True,'original_run_seal_unchanged':True,'original_score_upgraded':False,'candidate_origin':'NO_AGENT_PROPOSAL_OBSERVED'})
print(json.dumps({'diagnostic_run':diag.name,'status':r['overall_status'],'counts':r.get('test_results',{}).get('collected'),'patch_sha256':meta['sha256']}))
