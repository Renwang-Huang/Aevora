"""Bounded real native protocol preflight; public materials, no repair/evaluation claim."""
import pathlib,json,sys,shutil
from uuid import uuid4
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from integrations.agents import TaskInput,ExecutionContext
import integrations.codex_agent as runtime
from integrations.runtime_evidence import seal_run
archive=pathlib.Path(sys.argv[1]).resolve()
prepared=BenchmarkRunner(archive/'readonly-probe-runs').prepare('A');directory=archive/'readonly-probe-runs'/prepared['run_id'];participant=build_participant(directory/'workspace',directory/'participant')
original=runtime.native_command
def native(config,url):
 command=original(config,url);return command[:-1]+['--enable','code_mode_only',command[-1]]
runtime.native_command=native
config=runtime.CodexConfig.from_environment(model='gpt-5.6-terra',reasoning_effort='max',timeout_seconds=180,request_budget=24)
try:
 result=runtime.CodexAgentAdapter(config).execute(TaskInput('A','1.0.0','Read AGENTS.md and ISSUE.md. Delegate two distinct read-only investigations of the public code to two different native subagents, wait for both actual returns, and report the findings. Do not modify any app or test files. This is a runtime protocol probe, not a repair challenge.'),ExecutionContext(prepared['run_id'],str(participant),constraints={'archive':str(directory),'baseline':str(directory/'workspace')}))
 summary={'run_id':prepared['run_id'],'purpose':'LIVE_READONLY_PROTOCOL_PREFLIGHT_NOT_FORMAL_CHALLENGE','runtime':result.runtime_metadata,'execution_status':result.status.value}
 (archive/'readonly_probe_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'run_id':prepared['run_id'],'execution_status':result.status.value,'failure_kind':result.runtime_metadata.get('failure_kind'),'subagents':result.runtime_metadata.get('subagents',{}).get('verified_count'),'items':result.runtime_metadata.get('trace_observations',{}).get('completed_items')}))
finally:
 state=directory/'codex-state'
 if state.exists():shutil.rmtree(state)
 seal_run(directory)
