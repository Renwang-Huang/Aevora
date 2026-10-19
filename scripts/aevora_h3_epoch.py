"""Append-only H3 live source epochs; completed Runs keep their original pins."""
from dataclasses import replace
from pathlib import Path
import argparse
import json
import shutil
from scripts.aevora_h3_audit import archive,sources,ROOT,write,digest,now
from scripts.aevora_h2_junit import check_junit


def current():
    A=archive();p=A/'g1/EPOCH_CURRENT'
    return A/('g1/'+p.read_text().strip()) if p.exists() else A/'g1'


def admitted():
    A=archive();epoch=current();gate=json.loads((epoch/'LIVE_GATE.json').read_text())
    if gate['status']!='PASS_REQUIRED_FUNCTIONAL_EVIDENCE':raise ValueError('H3 current live gate missing')
    for p,value in gate['checks'].items():
        if digest(A/p)!=value:raise ValueError('Gate receipt changed: '+p)
    for p,row in gate['source_files'].items():
        if digest(ROOT/p)!=row['sha256']:raise ValueError('Active source epoch changed: '+p)
    return gate


def freeze(label,regression,security,release):
    A=archive();out=A/'g1'/label;out.mkdir(mode=0o700)
    required=json.loads((A/'g0/INHERITED_TEST_IDENTITIES.json').read_text())['identities']
    checked=check_junit(Path(regression)/'JUNIT.xml',required)
    if checked['status']!='PASS':raise ValueError('Full current JUnit including inherited identities failed')
    sec=json.loads(Path(security).read_text())
    if sec.get('status')!='PASS' or len(sec.get('checks',[]))<22:raise ValueError('Current security proof failed')
    rows=sources();manifest=json.loads(Path(release).read_text())
    if manifest['source_files']!=rows:raise ValueError('Exact source release mismatch')
    epoch=json.loads((Path(regression)/'SOURCE_EPOCH.json').read_text())
    if any(digest(ROOT/p)!=value for p,value in epoch.items()):raise ValueError('Tested Core changed')
    snapshot=out/'frozen_source_snapshot';snapshot.mkdir()
    for p,row in rows.items():
        destination=snapshot/p;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,destination);destination.chmod(row['mode'])
        if digest(destination)!=row['sha256']:raise ValueError('Epoch copy changed')
    write(out/'SOURCE_TRUST_MANIFEST.json',{'files':{'frozen_source_snapshot/'+p:r['sha256'] for p,r in rows.items()},
        'source_commit':manifest['commit'],'recorded_at':now(),'authority':'Trusted local source pin; not external attestation'})
    linked=[Path(regression)/'JUNIT.xml',Path(regression)/'RAW_RECEIPT.json',Path(security),Path(release),A/'g1/INTEGRITY_CURRENT.json']
    write(out/'LIVE_GATE.json',{'status':'PASS_REQUIRED_FUNCTIONAL_EVIDENCE','source_files':rows,
        'checks':{str(p.relative_to(A)):digest(p) for p in linked},'source_commit':manifest['commit'],
        'security':'PARTIAL_SHARED_KERNEL','model':'gpt-5.6-terra','effort':'max','completion_policy':'completion-aware',
        'timeout_seconds':None,'request_budget':None,'parallel_trials':1,'maximum_model_concurrency':4,'recorded_at':now()})
    # This is a current pointer, not a historical receipt modification.
    (A/'g1/EPOCH_CURRENT').write_text(label+'\n')
    print(json.dumps({'status':'PASS_REQUIRED_FUNCTIONAL_EVIDENCE','epoch':label,'source_commit':manifest['commit']}))


def challenge(label):
    from integrations.codex_agent import CodexConfig
    from benchmark.runner import BenchmarkRunner
    gate=admitted();A=archive();out=A/'g1/live'/label;out.mkdir(parents=True,mode=0o700)
    write(out/'SOURCE_EPOCH.json',{'source_epoch':str(current().relative_to(A)),
        'source_manifest_sha256':digest(current()/'SOURCE_TRUST_MANIFEST.json'),'source_commit':gate['source_commit']})
    config=replace(CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,
        request_budget=None,agent_mode='multi',experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max'),
        enable_experience_proposals=True)
    report=BenchmarkRunner(out/'runs').run_agent('A',config=config,variant='v01')
    value={k:report.get(k,'UNAVAILABLE') for k in ['run_id','overall_status','runtime_result','evaluation_result','multi_agent_status','failure_kind']}
    value.update(submission_sha256=report.get('agent',{}).get('submission_sha256'),kind='H3_NEW_NATIVE_ENGINEERING_SESSION',causal_benefit='UNKNOWN')
    write(out/'SUMMARY.json',value);admitted();print(json.dumps(value));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True)
    q=s.add_parser('freeze');q.add_argument('--label',required=True);q.add_argument('--regression',type=Path,required=True)
    q.add_argument('--security',type=Path,required=True);q.add_argument('--release',type=Path,required=True)
    q=s.add_parser('run');q.add_argument('--label',required=True)
    a=p.parse_args()
    if not a.label.isidentifier():raise ValueError('Simple unique epoch/trial label required')
    if a.op=='freeze':freeze(a.label,a.regression,a.security,a.release)
    else:raise SystemExit(challenge(a.label))
