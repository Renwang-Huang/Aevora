from pathlib import Path
import subprocess,json,datetime,time,hashlib,os,base64
E=Path(__file__).resolve().parent;P=E/'worktree'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def private_values():
 paths=[Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key'),*Path('/home/PRIVATE_MAINTAINER/.config/aevora/final-6312c046').rglob('*.password')]
 out=[]
 for p in paths:
  if p.is_file():
   b=p.read_bytes().strip()
   if len(b)>12:out += [b,base64.b64encode(b),hashlib.sha256(b).hexdigest().encode()]
 return out
def redact(b):
 for s in private_values():b=b.replace(s,b'[REDACTED_CREDENTIAL]')
 return b
def record(label,args,cwd=None,env=None):
 d=E/'commands'/label;d.mkdir(parents=True,exist_ok=False);start=now();t=time.monotonic();r=subprocess.run(list(map(str,args)),cwd=cwd or P,env=env,capture_output=True)
 outputs={}
 for name,b in [('stdout',r.stdout),('stderr',r.stderr)]:
  cleaned=redact(b);(d/(name+'.log')).write_bytes(cleaned);outputs[name]=dict(original_sha256=hashlib.sha256(b).hexdigest(),sha256=hashlib.sha256(cleaned).hexdigest(),redacted=cleaned!=b,original_bytes=len(b))
  if cleaned!=b:
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   key=Path('/home/PRIVATE_MAINTAINER/.config/aevora/final-6312c046/capture-aes.key')
   if not key.exists():key.write_bytes(os.urandom(32));key.chmod(0o600)
   nonce=os.urandom(12);cipher=AESGCM(key.read_bytes());(d/(name+'.raw.aesgcm')).write_bytes(nonce+cipher.encrypt(nonce,b,label.encode()))
 v=dict(argv=json.loads(redact(json.dumps(list(map(str,args))).encode())),cwd=str(cwd or P),start=start,end=now(),elapsed=time.monotonic()-t,exit=r.returncode,outputs=outputs);write(d/'receipt.json',v)
 with (E/'COMMAND_LOG.jsonl').open('a') as f:f.write(json.dumps(dict(label=label,**v))+'\n')
 return r.returncode
