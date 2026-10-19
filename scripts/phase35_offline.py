"""Scoped CLI regression and replay; writes only the new validation archive."""
import json,pathlib,subprocess,sys,hashlib,datetime,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
archive=pathlib.Path(sys.argv[1]).resolve(); out=archive/'offline';out.mkdir()
runroot=archive/'offline-runs'
base=[sys.executable,'-m','benchmark.cli','--runs-root',str(runroot)]
cases=[('smoke-buggy',['evaluate','--episode','SMOKE-001'],1),('smoke-reference',['evaluate','--episode','SMOKE-001','--submission',str(ROOT/'app')],0),('a-buggy',['evaluate','--episode','A'],1),('a-reference',['evaluate','--episode','A','--submission',str(ROOT/'app')],0),('original-phase3-replay',['evaluate','--episode','A','--submission',str(ROOT/'runs/339f7d73-29df-4242-8920-9e566bce8a9c/submission.diff')],0),*[(ep.lower()+'-planned',['evaluate','--episode',ep],4) for ep in ('B','C','D')],('submission-error',['evaluate','--episode','SMOKE-001','--submission',str(out/'absent.diff')],2),('evaluation-timeout',['evaluate','--episode','SMOKE-001','--timeout','0.001'],3)]
results=[]
for label,args,expected in cases:
 d=out/label;d.mkdir(); argv=base+args; started=datetime.datetime.now(datetime.timezone.utc).isoformat(); t=time.monotonic(); p=subprocess.run(argv,capture_output=True,timeout=120)
 (d/'stdout.log').write_bytes(p.stdout);(d/'stderr.log').write_bytes(p.stderr)
 report=json.loads(p.stdout) if p.stdout else None
 record={'label':label,'argv':argv,'exit_code':p.returncode,'expected_exit':expected,'started_at':started,'elapsed_seconds':time.monotonic()-t,'run_id':report.get('run_id') if report else None,'overall_status':report.get('overall_status') if report else None,'tests':report.get('test_results') if report else None,'submission_integrity':report.get('submission_integrity') if report else None,'fingerprints':report.get('fingerprints') if report else None}
 (d/'command.json').write_text(json.dumps(record,indent=2)+'\n');results.append(record);print(label,p.returncode,record['overall_status'],flush=True)
 assert p.returncode==expected, (label,p.stdout,p.stderr)
 if label=='original-phase3-replay':
  assert report['test_results']['passed']==report['test_results']['collected']==14
  assert report['submission_integrity']['patch_sha256']==hashlib.sha256((ROOT/'runs/339f7d73-29df-4242-8920-9e566bce8a9c/submission.diff').read_bytes()).hexdigest()
  old=json.loads((ROOT/'runs/339f7d73-29df-4242-8920-9e566bce8a9c/evaluation_report.json').read_text())
  record['historical_fingerprint_comparison']={key:{'historical':value,'current':report['fingerprints'].get(key),'equal':value==report['fingerprints'].get(key)} for key,value in old['fingerprints'].items()}
  (d/'command.json').write_text(json.dumps(record,indent=2)+'\n')
(out/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
