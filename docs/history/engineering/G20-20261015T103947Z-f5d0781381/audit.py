from pathlib import Path
import datetime,hashlib,json,os,subprocess,time
E=Path(__file__).resolve().parent;C=json.loads((E/'CONFIG.json').read_text());P=Path(C['worktree']);W=Path(C['main']);BASE=Path(C['base_source'])
os.umask(0o077)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n' if not isinstance(obj,str) else obj)
def record(label,argv,cwd=None):
 argv=list(map(str,argv));d=E/'commands'/label;d.mkdir();start=now();t=time.monotonic()
 env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','PYTHONDONTWRITEBYTECODE':'1','PYTHONPYCACHEPREFIX':str(E/'scratch_pycache')}
 with (d/'stdout.log').open('wb') as out,(d/'stderr.log').open('wb') as err:r=subprocess.run(argv,cwd=cwd or E,env=env,stdout=out,stderr=err)
 item={'label':label,'argv':argv,'cwd':str(cwd or E),'started_at':start,'ended_at':now(),'elapsed_seconds':time.monotonic()-t,'exit_code':r.returncode,'stdout_sha256':sha(d/'stdout.log'),'stderr_sha256':sha(d/'stderr.log')};write(d/'receipt.json',item)
 with (E/'COMMAND_LOG.jsonl').open('a') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
 print(label,r.returncode,flush=True);return r.returncode
if __name__=='__main__':
 import sys
 raise SystemExit(record(sys.argv[1],sys.argv[2:]))
