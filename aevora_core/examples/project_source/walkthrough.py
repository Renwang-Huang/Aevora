"""Synthetic public integration walkthrough; no model, private package or candidate execution.

Use an initialized dedicated graph and a new external output directory. This
checks an intentionally tiny file contract, not an engineering benefit claim.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from aevora.mcp_server import ExperienceService
from aevora.graph_repository import GraphRepository
from aevora.project_receipt import package_receipt
from aevora.project_source import POLICY_VERSION

FACTS = {'contract_version':'public-project-source-demo/v1',
         'concurrency_scope':'single_process_threads'}
SUITE = '''import os
from pathlib import Path
def test_contract():
    assert Path(os.environ["PROJECT_SUBMISSION"]).read_bytes() == b"contract-v1\\n"
'''
RUNNER = '''import os, subprocess, sys
os.environ["PROJECT_SUBMISSION"] = sys.argv[1]
raise SystemExit(subprocess.call([sys.executable,"-I","-m","pytest","-c","/dev/null",
    "--rootdir",os.path.dirname(sys.argv[2]),"-p","no:cacheprovider",
    "--junitxml="+sys.argv[3],sys.argv[2]], env=dict(os.environ)))
'''


def stamp(): return datetime.now(timezone.utc).isoformat()
def emit(path, value):
    with path.open('x') as f: json.dump(value,f,indent=2); f.write('\n')


def prepare_evidence(root, candidate, *, fail=False):
    """Run the independently owned, fixed demonstration suite with no DB credentials."""
    trusted = root/'trusted'; trusted.mkdir(mode=0o700)
    source = root/'submission.txt'; source.write_bytes(b'wrong\n' if fail else b'contract-v1\n')
    suite = trusted/'test_contract.py'; suite.write_text(SUITE)
    runner = trusted/'runner.py'; runner.write_text(RUNNER)
    policy = {'schema_version':POLICY_VERSION, 'verifier_id':'public-synthetic-verifier',
        'origin':'synthetic_or_test_fixture', 'facts':FACTS,
        'suite_sha256':sha256(suite.read_bytes()).hexdigest(),
        'evaluator_sha256':sha256(runner.read_bytes()).hexdigest(),
        'required_tests':['test_contract::test_contract']}
    policy_path = trusted/'policy.json'; emit(policy_path,policy); policy_path.chmod(0o600)
    candidate_path = root/'candidate.json'; emit(candidate_path,{'candidate':candidate})
    started = stamp()
    result = subprocess.run([sys.executable,'-I',str(runner),str(source),str(suite),str(root/'junit.xml')],
        cwd=trusted, env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),
                         'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}, capture_output=True)
    ended = stamp()
    (root/'verifier.stdout.log').write_bytes(result.stdout)
    (root/'verifier.stderr.log').write_bytes(result.stderr)
    receipt = package_receipt(candidate_file=candidate_path,policy_file=policy_path,
        artifacts={'submission':source,'suite':suite,'evaluator':runner,'junit':root/'junit.xml'},
        exit_code=result.returncode,started_at=started,ended_at=ended,output=root/'evidence')
    emit(root/'verifier-receipt.json',receipt)
    return policy_path, receipt['receipt_sha256'], result.returncode


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,help='Protected Host profile for a dedicated aevora_demo_ graph')
    a=p.parse_args(argv); output=a.output
    if not output.is_absolute() or output.exists(): raise ValueError('Fresh external absolute output required')
    if Path(__file__).resolve().parents[3] in output.parents:
        raise ValueError('Output must be outside the source checkout')
    from aevora.source_evidence import EvidenceFiles
    parent=EvidenceFiles(output.parent); parent.close()
    from aevora.host_config import prepare_environment
    prepare_environment(a.config)
    if not os.environ.get('AEVORA_FALKORDB_GRAPH','').startswith('aevora_demo_'):
        raise ValueError('Use an explicit dedicated aevora_demo_ graph, initialized with aevora init')
    output.mkdir(mode=0o700)
    run='project-demo-'+uuid.uuid4().hex[:12]
    repo=GraphRepository.from_environment()
    try:
        service=ExperienceService(run_id=run,public_context=FACTS,repository=repo,enable_proposals=True)
        proposal={'candidate_key':'file-contract','title':'Synthetic project source contract',
            'strategy':'Check the declared file contract before reusing this synthetic fixture',
            'public_summary':'Public integration fixture; no engineering benefit or native Agent claim.',
            'necessary_conditions':{k:[v] for k,v in FACTS.items()},
            'inapplicable_conditions':{},'scope':{k:[v] for k,v in FACTS.items()},
            'unknown_fields':[],'limitations':['Synthetic fixture; adoption and causal benefit UNKNOWN'],
            'source_references':[]}
        candidate_id=service.propose_experience(proposal)['candidate_id']
    finally: repo.close()
    def cli(label,*args):
        selection = ['--config',str(a.config)] if a.config else []
        r=subprocess.run([sys.executable,'-I','-m','aevora',*selection,*args],capture_output=True)
        (output/(label+'.stdout.json')).write_bytes(r.stdout)
        (output/(label+'.stderr.log')).write_bytes(r.stderr)
        if r.returncode: raise RuntimeError('CLI failed at '+label)
        return json.loads(r.stdout)
    def review(label,state,**extra):
        view=cli(label+'-inspect','inspect','--candidate',candidate_id)
        args=['review','--candidate',candidate_id,'--state',state,'--expected-head',view['head_sha256'],
              '--event-key',label,'--principal','public-demo-host','--reason','Explicit synthetic walkthrough']
        for key,value in extra.items(): args += ['--'+key,str(value)]
        return cli(label,*args)
    review('pending','EVIDENCE_PENDING')
    view=cli('candidate','inspect','--candidate',candidate_id)
    policy,pin,code=prepare_evidence(output,view['candidate'])
    if code: raise RuntimeError('Independent verifier failed; retained original logs')
    source=cli('source','source-project','--candidate',candidate_id,'--policy',str(policy),
               '--evidence-root',str(output/'evidence'),'--receipt-sha256',pin)
    scope=output/'scope.json'; emit(scope,{k:[v] for k,v in FACTS.items()})
    review('admit','ADMITTED_BOUNDED',source=source['source']['id'],scope=scope)
    published=review('publish','PUBLISHED')
    context=output/'context.json'; emit(context,FACTS)
    result=cli('next-query','query','--run-id',run+'-next','--context',str(context))
    row=next(x for x in result['candidates'] if x['experience_id']==published['experience_id'])
    if row['decision']!='APPLY': raise RuntimeError('Published fixture was not applicable')
    emit(output/'RESULT.json',{'status':'PASS','candidate_id':candidate_id,
        'experience_id':published['experience_id'],'next_run_decision':row['decision'],
        'origin':'synthetic_or_test_fixture','model_requests':0,'causal_benefit':'UNKNOWN'})
    print((output/'RESULT.json').read_text())


if __name__=='__main__': main()
