"""Actual negative submissions with a public, behavior-neutral payments comment.

These new manual Runs make strict submission provenance independently auditable
without shipping private reference repairs. No historical outcome is altered.
"""
import difflib,json
from pathlib import Path
from scripts.aevora_h4_audit import archive,ROOT,write,digest,now

def main(label):
    from benchmark.h2_cli import register_h2
    from benchmark.runner import BenchmarkRunner
    register_h2();A=archive();out=A/'g5'/label;out.mkdir(mode=0o700)
    before=(ROOT/'app/payments.py').read_text();after=before+'\n# H4 audit provenance check: no business behavior changed.\n'
    patch=out/'public-control.diff';patch.write_text(''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='a/app/payments.py',tofile='b/app/payments.py')))
    write(out/'PUBLIC_CONTROL_PATCH.json',{'sha256':digest(patch),'source_path':'app/payments.py','source_sha256':digest(ROOT/'app/payments.py'),'change':'A single behavior-neutral public comment; no private repair','at':now()})
    runner=BenchmarkRunner(out/'runs');rows=[]
    for episode,variant in [('SMOKE-001',None),('A','v01'),('D','v01'),('D-V02','v02')]:
        report=runner.evaluate(episode,patch,variant=variant);tests=report.get('test_results') or {};r=out/'runs'/report['run_id']/'evaluation_report.json'
        ok=report['overall_status']=='FAIL' and report.get('submission_integrity_status')=='PASS' and tests.get('collected',0)>0 and tests.get('failed',0)>0 and tests.get('errors')==tests.get('skipped')==0
        rows.append({'episode':episode,'variant':variant,'run_id':report['run_id'],'actual':report['overall_status'],'pytest_exit_code':report.get('pytest_exit_code'),'test_counts':{k:tests.get(k) for k in ['collected','passed','failed','errors','skipped']},'report_sha256':digest(r),'submission_sha256':report['submission_integrity']['patch_sha256'],'check':'PASS' if ok else 'FAIL'})
        with (out/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(rows[-1])+'\n')
    result={'status':'PASS' if all(r['check']=='PASS' for r in rows) else 'FAIL','rows':rows,'source_unchanged':digest(ROOT/'app/payments.py')==json.loads((out/'PUBLIC_CONTROL_PATCH.json').read_text())['source_sha256'],'reset_results':[runner.reset(e) for e in ['SMOKE-001','A','D','D-V02']],'scope':'Manual independent hidden negative controls; no native or task-success claim'};write(out/'RESULT.json',result);print(json.dumps(result));return 0 if result['status']=='PASS' and result['source_unchanged'] else 1

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);a=p.parse_args()
    if not a.label.replace('-','').isalnum():raise ValueError('Simple evidence label required')
    raise SystemExit(main(a.label))
