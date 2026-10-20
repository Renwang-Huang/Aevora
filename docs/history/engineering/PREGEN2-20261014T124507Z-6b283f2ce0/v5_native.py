"""One existing official Adapter invocation per operation, no agent orchestrator."""
from pathlib import Path
import sys,json,os,uuid,shutil,datetime
from dataclasses import asdict,replace
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now,C
from integrations.codex_agent import CodexConfig,CodexAgentAdapter
from integrations.agents import TaskInput,ExecutionContext
from benchmark.runner import BenchmarkRunner
from benchmark.manifest import load_manifest
from benchmark.participant import build_participant
from integrations.runtime_evidence import seal_run
from benchmark.h2_cli import register_h2
register_h2()
op=sys.argv[1]
protocol=json.loads((E/'06_live_agent/challenge_protocol_frozen.json').read_text())
assert protocol['model']=='gpt-5.6-terra' and protocol['effort']=='max'
sources=json.loads((E/'00_environment/repo_integrity.json').read_text())['source547_sha256']
P=E/'owned_runtime/source';assert all(sha(P/n)==h for n,h in sources.items())
def config(budget,experience='disabled',proposals=False):
 return replace(CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=budget,agent_mode='single',experience_mode=experience,model='gpt-5.6-terra',reasoning_effort='max',stream_idle_timeout_ms=3600000),max_request_concurrency=2,enable_experience_proposals=proposals)
def register(label,budget):
 ledger=E/'06_live_agent/session_admission.jsonl';rows=[json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
 assert len(rows)<4 and label not in [r['label'] for r in rows] and sum(r['request_budget'] for r in rows)+budget<=40
 with ledger.open('a') as f:f.write(json.dumps({'label':label,'request_budget':budget,'at':now(),'provider':'gateway','model':'gpt-5.6-terra','effort':'max','agent_mode':'single','native_new_process':'WILL_START; actual thread evidence required'})+'\n')
def summary(run,metadata,kind):
 data={'kind':kind,'run_id':run.name,'thread_id':metadata.get('thread_id'),'session_id':metadata.get('session_id'),'native_exit':metadata.get('exit_code'),'runtime_result':metadata.get('runtime_result'),'failure_kind':metadata.get('failure_kind'),'broker':metadata.get('model_broker'),'trace_observations':metadata.get('trace_observations'),'native_rollout_observations':metadata.get('native_rollout_observations'),'native_mode':'SINGLE','at':now()}
 write(run.parent.parent/'SUMMARY.json',data);return data
if op=='preflight':
 register('preflight',4);out=E/'06_live_agent/preflight';out.mkdir(mode=0o700);runner=BenchmarkRunner(out/'runs');prepared=runner.prepare('A','v01');run=out/'runs'/prepared['run_id'];p=build_participant(run/'workspace',run/'participant',agent_mode='single')
 task=('This is an explicitly read-only authenticated runtime preflight. Do not repair or modify app or tests. '
       'Read the public workspace and perform the public prerequisites, then report actual observations and the marker '+protocol['nonce']+'. '
       'Do not claim independent evaluation success. The read-only instruction takes precedence over generic repair workflow. Finish naturally.')
 try:
  result=CodexAgentAdapter(config(4)).execute(TaskInput('A',load_manifest('A').version,task,asdict(load_manifest('A'))),ExecutionContext(run.name,str(p),constraints={'archive':str(run),'baseline':str(run/'workspace')}))
  data=summary(run,result.runtime_metadata,'NEW_AUTHENTICATED_READONLY_PREFLIGHT_NOT_TASK_GRADE');print(json.dumps({k:data[k] for k in ['run_id','thread_id','native_exit','runtime_result','failure_kind']}))
 finally:
  state=run/'codex-state'
  if state.exists():shutil.rmtree(state)
  seal_run(run)
elif op=='s1':
 register('S1_engineering',28);out=E/'06_live_agent/s1';out.mkdir(mode=0o700)
 # Only public task input gains a nonce, via existing TaskInput construction.
 # No source file, fixture semantics, tests or evaluator are modified.
 import benchmark.runner as br
 original=br.TaskInput
 def nonce_task(episode,version,public_task,public_metadata=None):
  return original(episode,version,public_task+'\nIndependent audit Challenge ID: '+protocol['nonce']+'.',public_metadata or {})
 br.TaskInput=nonce_task
 try:report=BenchmarkRunner(out/'runs').run_agent('D',config=config(28,'aevora',True),variant='v01')
 finally:br.TaskInput=original
 run=out/'runs'/report['run_id'];m=json.loads((run/'runtime_metadata.json').read_text()) if (run/'runtime_metadata.json').exists() else {};data=summary(run,m,'NEW_NATIVE_SINGLE_ENGINEERING_SESSION')
 write(out/'REPORT_SUMMARY.json',{k:report.get(k) for k in ['run_id','overall_status','runtime_result','evaluation_result','integration_result','failure_kind','submission_integrity_status','environment_reset']})
 print(json.dumps({k:report.get(k) for k in ['run_id','overall_status','runtime_result','evaluation_result','failure_kind']}))
elif op=='s2':
 register('S2_inheritance',8);out=E/'06_live_agent/s2';out.mkdir(mode=0o700);runner=BenchmarkRunner(out/'runs');prepared=runner.prepare('D','v01');run=out/'runs'/prepared['run_id'];p=build_participant(run/'workspace',run/'participant',agent_mode='single')
 task=('This is an explicitly read-only experience evidence observation in a fresh session, not a repair challenge. '
       'Do not modify any code or tests. Read public.json and ISSUE.md. Retrieve current Aevora experiences through actual resolve_experience, '
       'then build_evidence_bundle for relevant returned candidates. Examine provenance, current lifecycle state and any recent independently observed outcomes; '
       'report actual IDs, WHEN/WHY and limits. Record your own untrusted APPLY/VERIFY/ABSTAIN interpretation where candidates exist. '
       'No prior session prompt, tool output or repair summary is supplied. Do not infer this fresh buggy task is repaired. '
       'The read-only instruction overrides generic repair workflow; a NO_PATCH adapter result is expected. Finish naturally.')
 before={str(x.relative_to(p)):sha(x) for x in (p/'app').rglob('*.py')}
 try:
  result=CodexAgentAdapter(config(8,'aevora')).execute(TaskInput('D',load_manifest('D').version,task,asdict(load_manifest('D'))),ExecutionContext(run.name,str(p),constraints={'archive':str(run),'baseline':str(run/'workspace')}))
  data=summary(run,result.runtime_metadata,'NEW_NATIVE_READONLY_SUCCESSOR_SESSION');after={str(x.relative_to(p)):sha(x) for x in (p/'app').rglob('*.py')};write(out/'SOURCE_UNCHANGED.json',{'app_unchanged':before==after,'before':before,'after':after,'evaluation':'NOT_EXECUTED'})
  print(json.dumps({k:data[k] for k in ['run_id','thread_id','native_exit','runtime_result','failure_kind']}))
 finally:
  state=run/'codex-state'
  if state.exists():shutil.rmtree(state)
  seal_run(run)
else:raise ValueError('Unknown one-session operation')
