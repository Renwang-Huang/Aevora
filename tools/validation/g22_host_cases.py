"""Generate fresh, private independent OrderFlow cases for Host admission tests.

Uses the unchanged Runner/Evaluator; no model, fake Outcome or altered Oracle.
This is a maintainer validation entry, excluded from public product releases.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,shutil
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.paths import fresh_external_output


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(output):
    output=fresh_external_output(Path(output),ROOT);output.mkdir(mode=0o700)
    runs=output/'runs';records=[]
    for label,submission,expected in [('reference',ROOT/'app',0),('buggy',None,1)]:
        argv=[sys.executable,'-m','benchmark.h2_cli','--runs-root',str(runs),'evaluate','--episode','A']
        if submission:argv+=['--submission',str(submission)]
        result=subprocess.run(argv,cwd=ROOT,capture_output=True)
        (output/(label+'-stdout.json')).write_bytes(result.stdout)
        (output/(label+'-stderr.log')).write_bytes(result.stderr)
        (output/(label+'-command.json')).write_text(json.dumps(dict(argv=argv,exit=result.returncode)))
        if result.returncode!=expected:raise RuntimeError('Independent case has unexpected real exit; raw failure retained')
        report=json.loads(result.stdout);run_id=report['run_id'];rd=runs/run_id
        original=json.loads((rd/'evaluation_report.json').read_text())
        if original['evaluation_status']!=('PASS' if expected==0 else 'FAIL'):raise RuntimeError('Independent verdict differs')
        files={str(p.relative_to(rd)):sha(p) for p in rd.rglob('*') if p.is_file() and not p.is_symlink()}
        seal=rd/'HOST_RUN_MANIFEST.json';seal.write_text(json.dumps(dict(files=files),sort_keys=True))
        records.append(dict(label=label,run_id=run_id,root=str(rd),manifest_sha256=sha(seal),
                            evaluator_sha=original['fingerprints']['evaluator']['sha256'],
                            suite_sha=original['fingerprints']['test_suite']['sha256'],
                            tree_sha=original['submission']['evaluated_sha256'],patch_sha=original['submission_integrity']['patch_sha256'],
                            exit=result.returncode,tests=original['test_results']))
    source=output/'source_archive';snap=source/'frozen_source_snapshot';snap.mkdir(parents=True)
    for f in (ROOT/'evaluator').rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            target=snap/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
    for name in ['benchmark/sandbox.py','benchmark/submission.py']:
        target=snap/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    files={str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file()}
    manifest=source/'SOURCE_MANIFEST.json';manifest.write_text(json.dumps(dict(files=files),sort_keys=True))
    (output/'CASES.json').write_text(json.dumps(dict(cases=records,source_root=str(source),source_manifest_sha256=sha(manifest),
        provenance='FRESH_OWNED_HOST_CONTROLLED_INDEPENDENT_RUNS',new_agent_sessions=0),indent=2))
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    print(json.dumps([dict(run_id=c['run_id'],exit=c['exit']) for c in generate(a.output)]))
