"""One official native Runner invocation, not an Agent orchestrator."""
from pathlib import Path
import sys,json,os,shutil
from dataclasses import replace
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from integrations.codex_agent import CodexConfig
from benchmark.runner import BenchmarkRunner
from integrations.runtime_evidence import seal_run
freeze=json.loads((E/'source/SOURCE_TRUST_MANIFEST.json').read_text())
for n,h in freeze['files'].items():assert sha(E/'owned_runtime/source'/n.removeprefix('frozen_source_snapshot/'))==h
def config(experience='disabled',proposals=False):
 c=replace(CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,
   request_budget=None,agent_mode='single',experience_mode=experience,model='gpt-5.6-terra',
   reasoning_effort='max',stream_idle_timeout_ms=3600000),max_request_concurrency=2,enable_experience_proposals=proposals)
 # Dataclass __post_init__ validates construction and replace; no validate API.
 assert c.request_budget is None and c.timeout_seconds is None
 return c
mode=sys.argv[1]
if mode=='preflight':label='01_c1_repairs/native_preflight';episode='SMOKE-001';cfg=config()
elif mode=='s1':label='02_live_s1';episode='D';cfg=config('aevora',True)
elif mode=='s2':
 label='04_live_s2';selection=json.loads((E/'03_feedback/S2_SELECTION.json').read_text());episode=selection['episode'];cfg=config('aevora',True)
else:raise ValueError('Unknown one-session operation')
out=E/label;out.mkdir(parents=True,exist_ok=True)
write(out/'SESSION_ADMISSION.json',{'at':now(),'phase':mode,'episode':episode,'policy':'completion-aware','request_budget':None,'timeout_seconds':None,'usd_budget':None,'token_budget':None,'agent_mode':'single','fresh_session_required':True,'source_manifest_sha256':sha(E/'source/SOURCE_TRUST_MANIFEST.json'),'no_previous_session_context_or_patch':True})
report=BenchmarkRunner(out/'runs').run_agent(episode,config=cfg,variant='v01' if episode in ('A','D') else None)
run=out/'runs'/report['run_id'];m=json.loads((run/'runtime_metadata.json').read_text())
write(out/'ORIGINAL_RUN_SUMMARY.json',{'at':now(),'phase':mode,'run_id':run.name,'native_exit':m.get('exit_code'),
 'thread_id':m.get('thread_id'),'session_id':m.get('session_id'),'runtime_result':report.get('runtime_result'),
 'evaluation_result':report.get('evaluation_result'),'integration_result':report.get('integration_result'),
 'overall_status':report['overall_status'],'failure_kind':report.get('failure_kind'),
 'test_results':report.get('test_results'),'report_sha256':sha(run/'evaluation_report.json'),
 'request_budget':m.get('request_budget'),'upstream_requests':m.get('model_broker',{}).get('upstream_requests'),
 'local_budget_rejections':sum(x.get('category')=='RUN_REQUEST_BUDGET_EXHAUSTED' for x in m.get('model_broker',{}).get('request_records',[])),
 'natural_original_run_only':True,'postmortem_upgrade':False})
assert m.get('request_budget') is None
assert not any(x.get('category')=='RUN_REQUEST_BUDGET_EXHAUSTED' for x in m.get('model_broker',{}).get('request_records',[]))
state=run/'codex-state'
if state.exists():shutil.rmtree(state)
# Experience-enabled Runner already seals the completed Run. Verify; never reseal.
manifest=run/'run_evidence_manifest.json'
if manifest.exists():
 sealed=json.loads(manifest.read_text())
 assert sealed['run_id']==run.name
 for n,h in sealed['files'].items():assert sha(run/n)==h
else:seal_run(run)
print(json.dumps({'phase':mode,'run_id':run.name,'native_exit':m.get('exit_code'),'runtime':report.get('runtime_result'),'evaluation':report.get('evaluation_result'),'overall_status':report['overall_status'],'test_count':(report.get('test_results') or {}).get('collected')}),flush=True)
raise SystemExit(0 if report['overall_status']=='PASS' else 1)
