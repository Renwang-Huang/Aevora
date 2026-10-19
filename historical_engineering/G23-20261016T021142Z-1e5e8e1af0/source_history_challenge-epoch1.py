"""One actual unchanged Runner/official Codex execution, not an Agent orchestrator."""
from audit import *
from dataclasses import replace
import sys
from benchmark.runner import BenchmarkRunner
from integrations.codex_agent import CodexConfig
label=sys.argv[1];mode=label.split('_')[0];assert mode in {'S1','S2'}
world=E/'03_world_accepted';gate=json.loads((E/'G23_LIVE_GATE.json').read_text());assert gate['status']=='PASS'
for name,h in gate['source_files'].items():assert sha(P/name)==h,name
bootstrap=world/(mode+'_BOOTSTRAP.json');assert bootstrap.is_file()
if mode=='S2':
 publication=json.loads((E/'04_live/S1/HOST_PUBLICATION.json').read_text());assert publication['status']=='PUBLICATION_COMMITTED'
 registered=json.loads((E/'04_live/S2_REGISTRATION.json').read_text());assert registered['s1_publication_sha256']==sha(E/'04_live/S1/HOST_PUBLICATION.json')
cfg=CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=None,agent_mode='multi',experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max',stream_idle_timeout_ms=3600000,enable_experience_proposals=True,experience_protocol_profile='aevora.mcp/2.0.0-rc2',experience_v2_bootstrap_path=bootstrap)
cfg=replace(cfg,max_request_concurrency=2)
out=E/'04_live'/label;out.mkdir(mode=0o700,parents=True,exist_ok=False)
write(out/'REGISTERED.json',{'at':now(),'mode':mode,'episode':'D','variant':'v01','source_gate_sha256':sha(E/'G23_LIVE_GATE.json'),'bootstrap_sha256':sha(bootstrap),'native_model':cfg.model,'effort':cfg.reasoning_effort,'agent_mode':'multi','timeout_seconds':None,'request_budget':None,'public_task_source':'unchanged public Episode Manifest, existing neutral Adapter instructions','no_specified_experience_id_in_prompt':True,'no_prior_rollout_or_patch_mounted':True})
report=BenchmarkRunner(out/'runs').run_agent('D',config=cfg,variant='v01')
run=out/'runs'/report['run_id'];metadata=json.loads((run/'runtime_metadata.json').read_text())
write(out/'ORIGINAL_RUN_SUMMARY.json',{'at':now(),'mode':mode,'run_id':run.name,'thread_id':metadata.get('thread_id'),'session_id':metadata.get('session_id'),'native_exit':metadata.get('exit_code'),'runtime_result':report.get('runtime_result'),'multi_agent_result':report.get('multi_agent_status'),'evaluation_result':report.get('evaluation_result'),'integration_result':report.get('integration_result'),'overall_status':report['overall_status'],'failure_kind':report.get('failure_kind'),'test_results':report.get('test_results'),'report_sha256':sha(run/'evaluation_report.json'),'request_budget':metadata.get('request_budget'),'upstream_requests':metadata.get('model_broker',{}).get('upstream_requests'),'native_verified_count':metadata.get('subagents',{}).get('verified_count'),'patch_sha256':sha(run/'submission.diff') if (run/'submission.diff').is_file() else None,'original_natural_run_only':True})
assert metadata.get('request_budget') is None
print(json.dumps({'mode':mode,'run_id':run.name,'status':report['overall_status'],'tests':report.get('test_results')}))
raise SystemExit(0 if report.get('integration_result')=='PASS' else 1)
