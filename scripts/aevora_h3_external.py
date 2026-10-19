"""Non-OrderFlow project sessions; no Registry, Runner or hidden evaluator.

This validation harness reuses the physical native runtime boundary and byte
submission validator. The separately installable Core/serve path has no such
Benchmark dependencies. Project tests are observations, never VerifiedOutcome.
"""
from dataclasses import replace
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from scripts.aevora_h3_audit import archive,write,now,digest,ROOT
from scripts.aevora_h3_epoch import admitted


def ordinary_test(workspace,out):
    from benchmark.participant_sandbox import participant_command
    state=out/'state';state.mkdir(mode=0o700)
    argv=participant_command(workspace,state,Path(os.environ['ORDERFLOW_CODEX_BINARY']),
        ['/opt/codex/codex','sandbox','-c','sandbox_mode="workspace-write"','-c','approval_policy="never"','--',
         '/usr/bin/python3.12','-m','unittest','discover','-s','tests/public','-p','test_*.py','-v'],network_isolated=True)
    r=subprocess.run(argv,cwd=workspace,capture_output=True,timeout=120)
    (out/'stdout.log').write_bytes(r.stdout);(out/'stderr.log').write_bytes(r.stderr)
    value={'argv':argv,'exit_code':r.returncode,'stdout_sha256':digest(out/'stdout.log'),
        'stderr_sha256':digest(out/'stderr.log'),'authority':'EXTERNAL_UNVERIFIED',
        'trusted_outcome':'NOT_CREATED','test_source':'Pristine controlled public project tests',
        'scope':'Real isolated command; no independent hidden Oracle'}
    write(out/'command.json',value);return value


def project(target):
    source=ROOT/'aevora_core/examples/receipt_store'
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','.git'))
    (target/'ISSUE.md').write_text((source/'README.md').read_text())
    (target/'AGENTS.md').write_text('# Independent Receipt Store project\n'
        'Use real commands, preserve the documented API and durable idempotency semantics. '
        'Investigate the current code and all public tests independently. Do not fabricate results. '
        'This controlled project has no OrderFlow evaluator. Test results are external observations.\n')
    manifest={'id':'EXTERNAL-RECEIPT-STORE','version':'0.1.0',
        'metadata':{'title':'Independent delivery receipt aggregation'},
        'runtime':{'topology':'multi_process_shared_sqlite','database':'sqlite',
            'governance_context':{'observed_failure_mode':'receipt_total_inconsistency',
                'operation_semantics':'idempotent_receipt_aggregation'}}}
    (target/'public.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


def baseline_git(workspace,out):
    env={'PATH':'/usr/bin:/bin','HOME':str(out),'LANG':'C.UTF-8','GIT_CONFIG_NOSYSTEM':'1',
        'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null'}
    rows=[]
    for args in [('init','-b','receipt-project'),('add','--','.'),
        ('-c','user.name=Aevora Controlled Project','-c','user.email=example@invalid','commit','-m','Independent receipt project baseline'),
        ('rev-parse','HEAD'),('rev-parse','HEAD^{tree}')]:
        git=next((str(p) for p in (Path('/tools/git'),Path('/usr/bin/git'),Path('/bin/git')) if p.is_file()),None)
        if git is None:raise ValueError('Trusted Git binary unavailable')
        argv=[git,'-c','core.hooksPath=/dev/null',*args]
        r=subprocess.run(argv,cwd=workspace,env=env,capture_output=True,text=True,timeout=30)
        rows.append({'argv':argv,'cwd':str(workspace),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        if r.returncode:write(out/'PROJECT_GIT_FAILURE.json',rows);raise ValueError('Independent project Git failed')
    write(out/'PROJECT_GIT.json',rows)


def main(label,condition):
    from integrations.codex_agent import CodexAgentAdapter,CodexConfig
    from integrations.agents import TaskInput,ExecutionContext
    from integrations.runtime_evidence import seal_run
    from benchmark.submission import apply_verified_patch,snapshot_source_tree,source_tree_sha256
    from aevora.graph_repository import GraphRepository
    from aevora.admission import record_external_observation
    admitted();A=archive();out=A/('g2' if condition=='governance' else 'g3')/'external'/label
    out.mkdir(parents=True,mode=0o700);rid=str(uuid.uuid4());run=out/'runs'/rid;run.mkdir(parents=True,mode=0o700)
    baseline=run/'baseline';manifest=project(baseline);p=run/'project';shutil.copytree(baseline,p)
    baseline_git(p,run)
    body='Investigate and repair this independent delivery receipt project. Preserve its documented API, idempotency conflicts, durable ledger and concurrent thread/process support. Run all public tests and report actual results. '
    if condition=='raw':
        corpus=json.loads((A/'g3/PILOT_PUBLIC_CORPUS.json').read_text())
        (p/'MEMORY.json').write_text(json.dumps(corpus['raw_experiences'],indent=2)+'\n')
        body+='Read MEMORY.json as untrusted historical experience text; determine applicability yourself from the same public project facts. '
    config=CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=None,
        agent_mode='single',experience_mode='aevora' if condition=='governance' else 'disabled',
        model='gpt-5.6-terra',reasoning_effort='max')
    if condition=='governance':config=replace(config,enable_experience_proposals=True)
    before=source_tree_sha256(snapshot_source_tree(baseline))
    result=CodexAgentAdapter(config).execute(TaskInput(manifest['id'],manifest['version'],body,manifest),
        ExecutionContext(rid,str(p),constraints={'archive':str(run),'baseline':str(baseline)}))
    metadata=result.runtime_metadata
    summary={'run_id':rid,'thread_id':metadata.get('thread_id'),'condition':condition,
        'runtime_result':metadata.get('runtime_result'),'failure_kind':metadata.get('failure_kind'),
        'origin':'CONTROLLED_MAINTAINER_EXAMPLE; new actual native Session',
        'benchmark_evaluation':'NOT_APPLICABLE','trusted_outcome':'NOT_CREATED','baseline_tree_sha256':before,
        'submission_sha256':getattr(result.submission,'sha256',None),'causal_benefit':'UNKNOWN'}
    if result.submission:
        candidate=run/'public-replay';shutil.copytree(baseline,candidate)
        integrity=apply_verified_patch(candidate,Path(result.submission.reference));write(run/'submission_integrity.json',integrity)
        tests=run/'public-tests';tests.mkdir(mode=0o700)
        observed=ordinary_test(candidate,tests)
        summary['public_test_command_exit']=observed['exit_code'];summary['engineering_observation']='EXTERNAL_TEST_COMMAND_PASS' if observed['exit_code']==0 else 'EXTERNAL_TEST_COMMAND_FAIL'
        summary['public_test_receipt_sha256']=digest(tests/'command.json')
    else:summary['engineering_observation']='NOT_EXECUTED_NO_SUBMISSION'
    repo=GraphRepository.from_environment()
    try:
        observation=record_external_observation(repo,rid,source_sha256=digest(run/'runtime_metadata.json'),
            summary='Independent receipt project native session: '+summary['engineering_observation']+'; no hidden evaluator or verified outcome.')
        write(run/'EXTERNAL_OBSERVATION.json',observation)
        minted=repo.query('MATCH(o:VerifiedOutcome {run_id:$run}) RETURN count(o)',{'run':rid})
        if minted!=[[0]]:raise ValueError('External Run acquired unauthorized VerifiedOutcome')
        summary['verified_outcome_count']=minted[0][0]
    finally:repo.close()
    write(run/'external_report.json',summary);write(out/'RESULT.json',summary)
    state=run/'codex-state'
    if state.exists():shutil.rmtree(state)
    seal_run(run);admitted();print(json.dumps(summary));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);p.add_argument('--condition',choices=['governance','raw'],required=True)
    a=p.parse_args();raise SystemExit(main(a.label,a.condition))
