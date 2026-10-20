from audit import *
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from integrations.codex_agent import CodexConfig,CodexAgentAdapter
from integrations.agents import TaskInput,ExecutionContext
from dataclasses import replace
from aevora.graph_repository import GraphRepository
import uuid
r=GraphRepository.from_environment();r.initialize(schema_version='aevora.graph/1.2');r.close()
from scripts.aevora_h2_security import Evidence,physical_probes
security=Evidence(E/'01_native/physical');physical_probes(security);assert security.finish('G23_NEW_PARTICIPANT_PHYSICAL')==0
root=E/'01_native/preflight';runner=BenchmarkRunner(root/'runs');report=runner.prepare('SMOKE-001');run=root/'runs'/report['run_id'];build_participant(run/'workspace',run/'participant')
(run/'participant/ISSUE.md').write_text('Native transport preflight. Delegate two independent read-only inspections: one inventories app modules, another reads public tests. Each child executes a tool and returns exact observations. Wait for both completions. Then create app/native_probe.py containing a short MODULE_COUNT integer based on observed files. Do not repair the business incident. Consult Aevora contextual evidence if useful; no experience usefulness or proposal is required.\n')
cfg=replace(CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=None,agent_mode='multi',experience_mode='aevora',stream_idle_timeout_ms=3600000),max_request_concurrency=2,enable_experience_proposals=True)
write(root/'REGISTERED.json',{'run':run.name,'task_sha':sha(run/'participant/ISSUE.md'),'source_epoch':'G22_UNCHANGED','request_budget':None,'timeout_seconds':None,'grading':'PREFLIGHT_NOT_BENCHMARK_OUTCOME'})
result=CodexAgentAdapter(cfg).execute(TaskInput('NATIVE-PREFLIGHT','1.0', (run/'participant/ISSUE.md').read_text(),{'runtime':{}}),ExecutionContext(run.name,str(run/'participant'),constraints={'archive':str(run),'baseline':str(run/'workspace')}))
write(root/'RESULT.json',result.to_dict());print(json.dumps({'status':result.status,'run':run.name,'subagents':result.runtime_metadata['subagents'],'failure':result.runtime_metadata['failure_kind']}))
raise SystemExit(0 if result.runtime_metadata.get('multi_agent_result')=='PASS' else 1)
