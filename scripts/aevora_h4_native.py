"""H4 ordinary native Codex sessions using the mature adapter, never an orchestrator."""
from dataclasses import replace
import argparse
import json
from pathlib import Path
import shutil
import uuid
from scripts.aevora_h4_audit import ROOT,archive,sources,write,digest,now


def admitted():
    a=archive();epoch=a/'g1'/ (a/'g1/EPOCH_CURRENT').read_text().strip()
    gate=json.loads((epoch/'LIVE_GATE.json').read_text())
    if gate['status']!='PASS_REQUIRED_FUNCTIONAL_EVIDENCE':raise ValueError('Current admission missing')
    for p,h in gate['receipts'].items():
        if digest(a/p)!=h:raise ValueError('Admission receipt changed')
    for p,row in gate['live_runtime_sources'].items():
        if digest(ROOT/p)!=row['sha256']:raise ValueError('Admitted runtime/input source changed: '+p)
    return epoch,gate


def freeze(label,release_path,regression_path=None,security_path=None,install_result=None):
    from scripts.aevora_h2_junit import check_junit
    a=archive();release=json.loads(Path(release_path).read_text());rows=sources()
    if release['source_files']!=rows:raise ValueError('Exact source release mismatch')
    required=json.loads((a/'g0/INHERITED_TEST_IDENTITIES.json').read_text())['identities']
    regression=Path(regression_path or a/'g1/full-regression');checked=check_junit(regression/'JUNIT.xml',required)
    if checked['status']!='PASS':raise ValueError('Full inherited regression failed')
    security=Path(security_path or a/'g1/security/summary.json');sec=json.loads(security.read_text())
    if sec['status']!='PASS' or len(sec['checks'])<22:raise ValueError('Current physical security gate failed')
    tested=json.loads((regression/'SOURCE_EPOCH.json').read_text())
    if any(digest(ROOT/p)!=h for p,h in tested.items()):raise ValueError('Tested Core changed')
    runtime={p:row for p,row in rows.items() if p.startswith(('aevora_core/src/','aevora_core/examples/receipt_store/','integrations/','benchmark/','evaluator/')) or p in ['scripts/aevora_h4_native.py','scripts/aevora_h3_external.py','scripts/aevora-h2-python','pyproject.toml']}
    epoch=a/'g1'/label;epoch.mkdir(mode=0o700);snapshot=epoch/'frozen_source_snapshot';snapshot.mkdir()
    for rel,row in rows.items():
        dest=snapshot/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest);dest.chmod(row['mode'])
        if digest(dest)!=row['sha256']:raise ValueError('Source snapshot changed')
    write(epoch/'SOURCE_TRUST_MANIFEST.json',{'files':{'frozen_source_snapshot/'+p:r['sha256'] for p,r in rows.items()},'source_commit':release['commit'],'source_tree':release['git_tree'],'at':now(),'authority':'Trusted local source pin; no external attestation'})
    linked=[a/'g0/GATE.json',regression/'JUNIT.xml',regression/'RAW_RECEIPT.json',security,Path(install_result or a/'g1/clean-onboarding-02/RESULT.json'),Path(release_path)]
    gate={'status':'PASS_REQUIRED_FUNCTIONAL_EVIDENCE','source_commit':release['commit'],'source_tree':release['git_tree'],
        'live_runtime_sources':runtime,'receipts':{str(p.relative_to(a)):digest(p) for p in linked},
        'security':'PARTIAL_SHARED_KERNEL','model':'gpt-5.6-terra','reasoning_effort':'max','completion_policy':'completion-aware',
        'agent_timeout':None,'request_budget':None,'parallel_trials':1,'maximum_model_concurrency':4,'at':now()}
    write(epoch/'LIVE_GATE.json',gate);(a/'g1/EPOCH_CURRENT').write_text(label+'\n')
    print(json.dumps({'status':gate['status'],'source_commit':gate['source_commit'],'source_files':len(rows),'live_runtime_sources':len(runtime)}))


def run(label,read_only=False):
    from scripts.aevora_h3_external import project,baseline_git,ordinary_test
    from integrations.codex_agent import CodexAgentAdapter,CodexConfig
    from integrations.agents import TaskInput,ExecutionContext
    from integrations.runtime_evidence import seal_run
    from benchmark.submission import apply_verified_patch,snapshot_source_tree,source_tree_sha256
    from aevora.graph_repository import GraphRepository
    from aevora.admission import record_external_observation
    epoch,gate=admitted();a=archive();out=a/('g1' if read_only else 'g4')/'native'/label;out.mkdir(parents=True,mode=0o700)
    rid=str(uuid.uuid4());run=out/'runs'/rid;run.mkdir(parents=True,mode=0o700)
    baseline=run/'baseline';manifest=project(baseline);workspace=run/'project';shutil.copytree(baseline,workspace);baseline_git(workspace,run)
    if read_only:
        body='This is a read-only Aevora onboarding check in an ordinary project. Inspect the actual public README, source and tests, call resolve_experience, and inspect build_evidence_bundle for an actually returned experience using its real query_id. Explain the returned scope, evidence and unknowns. You may record your own untrusted decision. Do not edit files, repair the code, or claim an engineering test success. Report actual tool results and any connection error.'
    else:
        body='Investigate and repair this independent delivery receipt project. Preserve its documented API, idempotency conflicts, durable ledger and concurrent thread/process support. Use available MCP experience tools if useful, judge their applicability from actual source and public project facts, run all original public tests and report actual results. Do not fabricate outcomes or disable concurrency.'
    config=CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,request_budget=None,
        agent_mode='single',experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max')
    config=replace(config,enable_experience_proposals=not read_only)
    write(run/'SOURCE_EPOCH.json',{'source_commit':gate['source_commit'],'source_tree':gate['source_tree'],
        'trust_manifest_sha256':digest(epoch/'SOURCE_TRUST_MANIFEST.json'),'epoch':str(epoch.relative_to(a)),'at':now()})
    before=source_tree_sha256(snapshot_source_tree(baseline))
    result=CodexAgentAdapter(config).execute(TaskInput(manifest['id'],manifest['version'],body,manifest),ExecutionContext(rid,str(workspace),constraints={'archive':str(run),'baseline':str(baseline)}))
    meta=result.runtime_metadata;requests=[];responses=[];p=run/'aevora_mcp_events.jsonl'
    if p.exists():
        for raw in p.read_bytes().splitlines(keepends=True):
            evt=json.loads(raw)
            if evt.get('category')!='JSONRPC':continue
            msg=json.loads(evt['raw_json'])
            if msg.get('method')=='tools/call':requests.append(msg.get('params',{}).get('name'))
            content=msg.get('result',{}).get('structuredContent')
            if isinstance(content,dict) and 'query_id' in content and 'candidates' in content:responses.append({'query_id':content['query_id'],'status':content.get('status'),'candidate_count':len(content['candidates'])})
    summary={'run_id':rid,'session_id':meta.get('session_id'),'runtime_result':meta.get('runtime_result'),'native_exit_code':meta.get('exit_code'),
        'failure_kind':meta.get('failure_kind'),'read_only':read_only,'actual_mcp_tool_calls':requests,'actual_query_responses':responses,
        'model':meta.get('model'),'provider':meta.get('provider'),'source_commit':gate['source_commit'],'source_tree':gate['source_tree'],
        'baseline_tree_sha256':before,'submission_sha256':getattr(result.submission,'sha256',None),'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN',
        'authority':'EXTERNAL_UNVERIFIED','trusted_outcome':'NOT_CREATED'}
    if result.submission:
        candidate=run/'public-replay';shutil.copytree(baseline,candidate)
        write(run/'submission_integrity.json',apply_verified_patch(candidate,Path(result.submission.reference)))
        tests=run/'public-tests';tests.mkdir(mode=0o700);observed=ordinary_test(candidate,tests)
        summary.update(public_test_command_exit=observed['exit_code'],public_test_receipt_sha256=digest(tests/'command.json'),
            engineering_observation='EXTERNAL_TEST_COMMAND_PASS' if observed['exit_code']==0 else 'EXTERNAL_TEST_COMMAND_FAIL')
    else:summary['engineering_observation']='NOT_EXECUTED_NO_SUBMISSION'
    summary['source_unchanged']=source_tree_sha256(snapshot_source_tree(workspace))==before
    if read_only:
        has_candidates=any(r['status']=='AVAILABLE' and r['candidate_count']>0 for r in responses)
        required_tools={'resolve_experience','build_evidence_bundle'} if has_candidates else {'resolve_experience'}
        summary['observation_status']='PASS' if meta.get('exit_code')==0 and meta.get('session_id') and summary['source_unchanged'] and required_tools<=set(requests) and responses and any(r['status']=='AVAILABLE' for r in responses) else 'FAIL'
        summary['bundle_requirement']='REQUIRED_FOR_ACTUALLY_RETURNED_CANDIDATES' if has_candidates else 'NOT_REQUIRED_EMPTY_ACTUAL_QUERY'
    repo=GraphRepository.from_environment()
    try:
        observation=record_external_observation(repo,rid,source_sha256=digest(run/'runtime_metadata.json'),summary='H4 actual ordinary native Session: '+summary['engineering_observation']+'; external observation, no trusted Oracle.')
        write(run/'EXTERNAL_OBSERVATION.json',observation)
        actual=repo.query('MATCH(n:VerifiedOutcome {run_id:$run}) RETURN count(n)',{'run':rid})
        if actual!=[[0]]:raise ValueError('External Run minted a trusted Outcome')
        summary['verified_outcome_count']=actual[0][0]
    finally:repo.close()
    write(run/'external_report.json',summary);write(out/'RESULT.json',summary)
    state=run/'codex-state'
    if state.exists():shutil.rmtree(state)
    seal_run(run);admitted();print(json.dumps(summary));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='op',required=True)
    q=sub.add_parser('freeze');q.add_argument('--label',required=True);q.add_argument('--release',type=Path,required=True)
    q.add_argument('--regression',type=Path);q.add_argument('--security',type=Path);q.add_argument('--install-result',type=Path)
    q=sub.add_parser('run');q.add_argument('--label',required=True);q.add_argument('--read-only',action='store_true');args=p.parse_args()
    if not args.label.replace('_','').replace('-','').isalnum():raise ValueError('Unique simple label required')
    if args.op=='freeze':freeze(args.label,args.release,args.regression,args.security,args.install_result)
    else:raise SystemExit(run(args.label,args.read_only))
