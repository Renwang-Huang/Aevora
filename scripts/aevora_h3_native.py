"""H3 source admission and fresh official sessions, with real independent grading."""
from dataclasses import replace, asdict
from hashlib import sha256
import argparse
import json
from pathlib import Path
import shutil
import sys
from scripts.aevora_h3_audit import archive, sources, digest, write, now, ROOT
from scripts.aevora_h2_junit import check_junit


def freeze(regression, security, release):
    A=archive(); regression=Path(regression);security=Path(security);release=Path(release)
    required=json.loads((A/'g0/INHERITED_TEST_IDENTITIES.json').read_text())['identities']
    test=check_junit(regression/'JUNIT.xml',required)
    if test['status']!='PASS':raise ValueError('All inherited current identities must pass')
    sec=json.loads(security.read_text())
    if sec.get('status')!='PASS' or sec.get('model_calls')!=0 or len(sec.get('checks',[]))<22:
        raise ValueError('Current physical and scoped proposal security proof required')
    rows=sources(); manifest=json.loads(release.read_text())
    if manifest['source_files']!=rows:raise ValueError('Release does not pin exact current source')
    epoch=json.loads((regression/'SOURCE_EPOCH.json').read_text())
    if any(digest(ROOT/p)!=value for p,value in epoch.items()):raise ValueError('Tested Core changed')
    snapshot=A/'g1/frozen_source_snapshot';snapshot.mkdir(mode=0o700)
    for rel,row in rows.items():
        dest=snapshot/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest);dest.chmod(row['mode'])
        if digest(dest)!=row['sha256']:raise ValueError('Freeze bytes changed')
    write(A/'g1/SOURCE_TRUST_MANIFEST.json',{'files':{'frozen_source_snapshot/'+p:r['sha256'] for p,r in rows.items()},
        'created_at':now(),'source_commit':manifest['commit'],'authority':'Trusted local source pin; not external attestation'})
    links={str(p.relative_to(A)):digest(p) for p in [regression/'JUNIT.xml',regression/'RAW_RECEIPT.json',security,release,A/'g0/GATE.json']}
    write(A/'g1/LIVE_GATE.json',{'status':'PASS_REQUIRED_FUNCTIONAL_EVIDENCE','overall_security':'PARTIAL',
        'source_files':rows,'checks':links,'source_commit':manifest['commit'],
        'model':'gpt-5.6-terra','reasoning_effort':'max','completion_policy':'completion-aware','agent_timeout':None,
        'request_budget':None,'parallel_trials':1,'maximum_model_concurrency':4,'operator_cancel':'Trusted runtime control file/CLI',
        'native_uds_compatibility':'PARTIAL; original errors retained; equivalent in-process public assertions passed'})
    print(json.dumps({'status':'PASS_REQUIRED_FUNCTIONAL_EVIDENCE','commit':manifest['commit'],'source_files':len(rows)}))


def admitted():
    A=archive();gate=json.loads((A/'g1/LIVE_GATE.json').read_text())
    if gate['status']!='PASS_REQUIRED_FUNCTIONAL_EVIDENCE':raise ValueError('H3 live admission missing')
    for p,value in gate['checks'].items():
        if digest(A/p)!=value:raise ValueError('Gate evidence changed: '+p)
    # Docs added after a completed gate are not active execution source. Existing
    # pinned source files must still match while each real session is active.
    for p,row in gate['source_files'].items():
        if digest(ROOT/p)!=row['sha256']:raise ValueError('Frozen live source changed: '+p)
    return gate


def challenge(label,episode='A',variant='v01',agent_mode='multi'):
    from integrations.codex_agent import CodexConfig
    from benchmark.runner import BenchmarkRunner
    from benchmark.h2_cli import register_h2
    admitted();A=archive();out=A/'g1/live'/label;out.mkdir(parents=True,mode=0o700)
    register_h2()
    config=replace(CodexConfig.from_environment(completion_policy='completion-aware',timeout_seconds=None,
        request_budget=None,agent_mode=agent_mode,experience_mode='aevora',model='gpt-5.6-terra',reasoning_effort='max'),
        enable_experience_proposals=True)
    report=BenchmarkRunner(out/'runs').run_agent(episode,config=config,variant=variant)
    summary={'run_id':report['run_id'],'overall_status':report['overall_status'],
        'runtime_result':report.get('runtime_result','UNAVAILABLE'),'evaluation_result':report.get('evaluation_result','UNAVAILABLE'),
        'multi_agent_status':report.get('multi_agent_status','UNAVAILABLE'),'submission_sha256':report.get('agent',{}).get('submission_sha256'),
        'kind':'H3_NEW_NATIVE_ENGINEERING_SESSION','causal_benefit':'UNKNOWN','failure_kind':report.get('failure_kind')}
    write(out/'SUMMARY.json',summary);admitted();print(json.dumps(summary));return 0


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True)
    q=s.add_parser('freeze');q.add_argument('--regression',required=True);q.add_argument('--security',required=True);q.add_argument('--release',required=True)
    q=s.add_parser('run');q.add_argument('--label',required=True);q.add_argument('--episode',default='A');q.add_argument('--variant',default='v01');q.add_argument('--agent-mode',default='multi',choices=['single','multi'])
    a=p.parse_args()
    if a.op=='freeze':freeze(a.regression,a.security,a.release);return 0
    if not a.label.isidentifier():raise ValueError('Simple unique trial label required')
    return challenge(a.label,a.episode,a.variant,a.agent_mode)


if __name__=='__main__':raise SystemExit(main())
