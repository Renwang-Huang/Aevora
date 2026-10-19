from pathlib import Path
import json,subprocess,sys,hashlib,shutil
E=Path(__file__).parent;P=E/'worktree';O=E/'01_admission/verified-runs';O.mkdir();runs=O/'runs'
records=[]
for label,submission in [('reference',P/'app'),('buggy',None)]:
 argv=[sys.executable,'-m','benchmark.h2_cli','--runs-root',str(runs),'evaluate','--episode','A']
 if submission:argv += ['--submission',str(submission)]
 r=subprocess.run(argv,capture_output=True)
 (O/(label+'-stdout.json')).write_bytes(r.stdout);(O/(label+'-stderr.log')).write_bytes(r.stderr)
 row=json.loads(r.stdout);rid=row['run_id'];rd=runs/rid
 assert r.returncode==(0 if label=='reference' else 1),(r.returncode,r.stderr[-2000:])
 report=json.loads((rd/'evaluation_report.json').read_text())
 assert report['evaluation_status']==('PASS' if label=='reference' else 'FAIL')
 files={str(f.relative_to(rd)):hashlib.sha256(f.read_bytes()).hexdigest() for f in rd.rglob('*') if f.is_file() and not f.is_symlink()}
 manifest=rd/'HOST_RUN_MANIFEST.json';manifest.write_text(json.dumps({'files':files},sort_keys=True))
 records.append(dict(label=label,run_id=rid,root=str(rd),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),evaluator_sha=report['fingerprints']['evaluator']['sha256'],suite_sha=report['fingerprints']['test_suite']['sha256'],tree_sha=report['submission']['evaluated_sha256'],patch_sha=report['submission_integrity']['patch_sha256'],exit=r.returncode,tests=report['test_results']))
source=O/'source_archive';snap=source/'frozen_source_snapshot';snap.mkdir(parents=True)
for f in (P/'evaluator').rglob('*'):
 if f.is_file() and '__pycache__' not in f.parts:
  target=snap/f.relative_to(P);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
for name in ['benchmark/sandbox.py','benchmark/submission.py']:
 target=snap/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/name,target)
files={str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source.rglob('*') if f.is_file()}
manifest=source/'SOURCE_MANIFEST.json';manifest.write_text(json.dumps({'files':files},sort_keys=True))
(O/'CASES.json').write_text(json.dumps({'cases':records,'source_root':str(source),'source_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},indent=2))
print([(r['label'],r['run_id'],r['exit']) for r in records])
