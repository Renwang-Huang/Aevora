from pathlib import Path
import subprocess,json,datetime,time,hashlib,os
E=Path(__file__).resolve().parent; P=E/'worktree'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def record(label,args,cwd=None,env=None):
 d=E/'commands'/label;d.mkdir(parents=True,exist_ok=False);start=now();t=time.monotonic()
 with (d/'stdout.log').open('xb') as out,(d/'stderr.log').open('xb') as err:
  r=subprocess.run(list(map(str,args)),cwd=cwd or P,env=env,stdout=out,stderr=err)
 v=dict(argv=list(map(str,args)),cwd=str(cwd or P),start=start,end=now(),elapsed=time.monotonic()-t,exit=r.returncode,stdout_sha256=sha(d/'stdout.log'),stderr_sha256=sha(d/'stderr.log'));write(d/'receipt.json',v)
 with (E/'COMMAND_LOG.jsonl').open('a') as f:f.write(json.dumps(dict(label=label,**v))+'\n')
 return r.returncode
