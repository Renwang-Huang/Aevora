"""Different fresh native Session reads a real publication; no task grade minted."""
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import shutil
from scripts.aevora_h3_audit import archive,write
from scripts.aevora_h3_epoch import admitted
from scripts.aevora_h2_native import observation_inputs


def main(label,experience_id):
    from benchmark.runner import BenchmarkRunner
    from benchmark.manifest import load_manifest
    from benchmark.participant import build_participant
    from integrations.agents import TaskInput,ExecutionContext
    from integrations.codex_agent import CodexConfig,CodexAgentAdapter
    from integrations.runtime_evidence import seal_run
    admitted();out=archive()/'g1/readback'/label;out.mkdir(parents=True,mode=0o700)
    runner=BenchmarkRunner(out/'runs');prepared=runner.prepare('A','v01');run=out/'runs'/prepared['run_id']
    p=build_participant(run/'workspace',run/'participant',agent_mode='single');before=observation_inputs(p)
    task=('This is an explicitly read-only evidence observation, not an engineering repair. Do not change code or tests. '
          'Read public.json and ISSUE.md, use actual Aevora resolve_experience and build_evidence_bundle for the returned '
          'experience '+experience_id+'. Report actual query, snapshot, candidate-lifecycle and source IDs, WHEN/WHY '
          'and UNKNOWN causal attribution. Record your evidence interpretation as an untrusted decision. '
          'Do not invent an outcome or infer the current task is fixed. This read-only instruction takes precedence '
          'over generic repair workflow; a NO_PATCH repair-adapter result is expected. Finish naturally.')
    c=CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=None,
       agent_mode='single',experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max')
    try:
        result=CodexAgentAdapter(c).execute(TaskInput('A',load_manifest('A').version,task,asdict(load_manifest('A'))),
            ExecutionContext(run.name,str(p),constraints={'archive':str(run),'baseline':str(run/'workspace')}))
        m=result.runtime_metadata;unchanged=observation_inputs(p)==before
        complete=m.get('trace_observations',{}).get('integrity',{}).get('status')=='COMPLETE'
        raw=[json.loads(l) for l in (run/'codex_events.jsonl').read_text().splitlines()]
        completed=[e['item'] for e in raw if e.get('item',{}).get('type')=='mcp_tool_call' and e['item'].get('status')=='completed']
        bundles=[i for i in completed if i.get('tool')=='build_evidence_bundle' and i.get('arguments',{}).get('experience_id')==experience_id and not i.get('error')]
        summary={'run_id':run.name,'thread_id':m.get('thread_id'),'kind':'H3_NEW_READ_ONLY_SESSION',
            'runtime_result':m.get('runtime_result'),'failure_kind':m.get('failure_kind'),'evaluation':'NOT_EXECUTED',
            'source_unchanged':unchanged,'native_turn_complete':complete,'target_experience_id':experience_id,
            'typed_native_bundle_events':len(bundles),'causal_influence':'UNKNOWN',
            'status':'PASS' if complete and unchanged and bundles and m.get('failure_kind')=='NO_PATCH' else 'PARTIAL'}
        write(run/'observation_report.json',summary);write(out/'RESULT.json',summary)
    finally:
        state=run/'codex-state'
        if state.exists():shutil.rmtree(state)
        seal_run(run)
    admitted();print(json.dumps(summary));return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);p.add_argument('--experience',required=True)
    a=p.parse_args();raise SystemExit(main(a.label,a.experience))
