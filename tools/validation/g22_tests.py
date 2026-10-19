"""Versioned lossless multi-process Cypher evidence collector, actual pytest.

Reuses the established owned SAVE/maintenance guard. Segments are finite; total
records are not truncated. Child process output has its own stream and final
counts derive from actual files, not the parent's counters.
"""
from pathlib import Path
import argparse,os,sys,json,time,hashlib,threading,fcntl
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from aevora.graph_repository import GraphRepository
from aevora.models import canonical_json
from tools.paths import fresh_external_output
from tools.validation.regression import owned_maintenance

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def epoch():
 return {str(p.relative_to(ROOT)):sha(p) for folder in ['aevora_core/src','aevora_maintainer','aevora_core/tests/g22','tools/validation'] for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--owned-port',type=int,required=True);p.add_argument('pytest_args',nargs=argparse.REMAINDER);a=p.parse_args()
 out=fresh_external_output(a.output,ROOT);out.mkdir(mode=0o700);raw=out/'cypher';raw.mkdir();before=epoch()
 (out/'SOURCE_EPOCH.json').write_text(json.dumps(before,sort_keys=True))
 os.environ['AEVORA_G22_ARTIFACT_ROOT']=str(out/'artifacts');os.environ['AEVORA_G21_ARTIFACT_ROOT']=str(out/'artifacts/G21_SDK')
 original=GraphRepository.query;lock=threading.Lock();segments={}
 def query(repo,statement,params=None,*,read_only=True):
  start=time.time_ns();t=time.monotonic();result=[];status='ERROR';error=None
  try:
   result=original(repo,statement,params,read_only=read_only);status='RETURNED';return result
  except BaseException as ex:error=type(ex).__name__;raise
  finally:
   row=dict(pid=os.getpid(),thread_id=threading.get_ident(),graph=repo.graph_name,statement=statement,params=params or {},read_only=read_only,start_ns=start,end_ns=time.time_ns(),seconds=time.monotonic()-t,status=status,error=error,rows=result)
   data=(canonical_json(row)+'\n').encode();assert len(data)<=64*1024*1024,'Single evidence record exceeds finite limit'
   with lock:
    pid=os.getpid();n=segments.get(pid,0);path=raw/(str(pid)+'-'+str(n)+'.jsonl')
    if path.exists() and path.stat().st_size+len(data)>128*1024*1024:n+=1;segments[pid]=n;path=raw/(str(pid)+'-'+str(n)+'.jsonl')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
    try:
     fcntl.flock(fd,fcntl.LOCK_EX);offset=0
     while offset<len(data):offset+=os.write(fd,data[offset:])
    finally:os.close(fd)
 repo=GraphRepository.from_environment();GraphRepository.query=query
 code=None
 try:
  import pytest
  args=a.pytest_args[1:] if a.pytest_args[:1]==['--'] else a.pytest_args
  with owned_maintenance(out,repo,a.owned_port):code=pytest.main([*args,'--junitxml='+str(out/'JUNIT.xml')])
 finally:
  GraphRepository.query=original;repo.close()
  files=[]
  for f in sorted(raw.glob('*.jsonl')):
   count=0
   with f.open() as src:
    for line in src:json.loads(line);count+=1
   files.append(dict(path=str(f.relative_to(out)),bytes=f.stat().st_size,records=count,sha256=sha(f)))
  (out/'RAW_RECEIPT.json').write_text(json.dumps(dict(files=files,records=sum(f['records'] for f in files),bytes=sum(f['bytes'] for f in files),pytest_exit=code),indent=2))
  after=epoch();(out/'SOURCE_UNCHANGED.json').write_text(json.dumps(dict(unchanged=before==after,before=before,after=after),sort_keys=True))
  assert before==after,'Execution source changed during validation'
 return code
if __name__=='__main__':raise SystemExit(main())
