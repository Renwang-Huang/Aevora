"""External read-only-baseline audit collector, not product code."""
import os,json,hashlib,datetime,time,subprocess
os.umask(0o077)
from pathlib import Path
E=Path(__file__).resolve().parent
C=json.loads((E/'CONFIG.json').read_text())
W=Path(C['active']);G5=Path(C['g5']);T=Path(C['archive'])
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(data,f,indent=2,sort_keys=True);f.write('\n')
def record(label,argv,cwd=None,env=None):
 d=E/'commands'/label;d.mkdir(mode=0o700,exist_ok=False)
 started=now();clock=time.monotonic()
 e=os.environ.copy();e.update({'PYTHONDONTWRITEBYTECODE':'1','GIT_OPTIONAL_LOCKS':'0','GIT_CONFIG_NOSYSTEM':'1'});e.update(env or {})
 with (d/'stdout.log').open('xb') as out,(d/'stderr.log').open('xb') as err:
  p=subprocess.run(list(map(str,argv)),cwd=cwd or E,env=e,stdout=out,stderr=err)
 r={'label':label,'argv':list(map(str,argv)),'cwd':str(cwd or E),'started_at':started,'ended_at':now(),'elapsed_seconds':time.monotonic()-clock,'exit_code':p.returncode,'stdout_sha256':sha(d/'stdout.log'),'stderr_sha256':sha(d/'stderr.log')}
 write(d/'receipt.json',r)
 with (E/'00_environment/commands.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 print(label,p.returncode,flush=True);return p.returncode
