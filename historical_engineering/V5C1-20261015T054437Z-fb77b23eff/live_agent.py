"""One actual official Codex/Runner Session, not an orchestrator or repair helper."""
from pathlib import Path
import sys,json,shutil
from dataclasses import replace
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from benchmark.h2_cli import register_h2
register_h2()
from integrations.codex_agent import CodexConfig
from benchmark.runner import BenchmarkRunner
from integrations.runtime_evidence import seal_run
mode=sys.argv[1];assert mode in {'S1','S2'}
gate=json.loads((E/'03_regression/G3_LIVE_ADMISSION.json').read_text());assert gate['status']=='PASS'
freeze=json.loads((E/'source/SOURCE_TRUST_MANIFEST.json').read_text())
for n,h in freeze['files'].items():assert sha(E/'owned_runtime/source'/n.removeprefix('frozen_source_snapshot/'))==h
cfg=replace(CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=None,agent_mode='single',experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max',stream_idle_timeout_ms=3600000),max_request_concurrency=2,enable_experience_proposals=True)
assert cfg.timeout_seconds is None and cfg.request_budget is None
out=E/'04_live'/mode;out.mkdir(exist_ok=False)
write(out/'SESSION_ADMISSION.json',{'at':now(),'phase':mode,'episode':'D-V02','variant':'v02','completion_policy':'completion-aware','timeout_seconds':None,'request_budget':None,'dollar_budget':None,'token_budget':None,'model':'gpt-5.6-terra','reasoning_effort':'max','agent_mode':'single','max_request_concurrency':2,'fresh_session_required':True,'source_manifest_sha256':sha(E/'source/SOURCE_TRUST_MANIFEST.json'),'g3_gate_sha256':sha(E/'03_regression/G3_LIVE_ADMISSION.json'),'preregistration_sha256':sha(E/'04_live/EXPERIMENT_PREREGISTRATION_RECEIPT.json'),'no_prior_patch_or_rollout_in_task_input':True})
report=BenchmarkRunner(out/'runs').run_agent('D-V02',config=cfg,variant='v02')
run=out/'runs'/report['run_id'];m=json.loads((run/'runtime_metadata.json').read_text())
write(out/'ORIGINAL_RUN_SUMMARY.json',{'at':now(),'phase':mode,'run_id':run.name,'native_exit':m.get('exit_code'),'thread_id':m.get('thread_id'),'session_id':m.get('session_id'),'runtime_result':report.get('runtime_result'),'evaluation_result':report.get('evaluation_result'),'integration_result':report.get('integration_result'),'overall_status':report['overall_status'],'failure_kind':report.get('failure_kind'),'test_results':report.get('test_results'),'report_sha256':sha(run/'evaluation_report.json'),'request_budget':m.get('request_budget'),'upstream_requests':m.get('model_broker',{}).get('upstream_requests'),'natural_original_run_only':True,'postmortem_upgrade':False})
assert m.get('request_budget') is None
assert not any(x.get('category')=='RUN_REQUEST_BUDGET_EXHAUSTED' for x in m.get('model_broker',{}).get('request_records',[]))
# Runner seals experience-enabled completed runs itself. Verify, never reseal.
manifest=run/'run_evidence_manifest.json'
if manifest.exists():
 sealed=json.loads(manifest.read_text());assert sealed['run_id']==run.name
 for name,h in sealed['files'].items():assert sha(run/name)==h
else:seal_run(run)
state=run/'codex-state'
if state.exists():shutil.rmtree(state) # ephemeral scoped runtime state, after writers stop; not original evidence
print(json.dumps({'phase':mode,'run_id':run.name,'native_exit':m.get('exit_code'),'overall_status':report['overall_status'],'test_results':report.get('test_results')}),flush=True)
raise SystemExit(0 if report['overall_status']=='PASS' else 1)
