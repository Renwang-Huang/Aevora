"""Terminal seal. Do not invoke through an in-Full recorder or write inside Full afterwards."""
from pathlib import Path
import os,stat,json,hashlib,datetime,zipfile
E=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
# Real known credential values/hashes remain in memory only, never printed or retained.
secret_paths=[Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')]
for cfg in ['RUNTIME_CONFIG.json','PERF_RUNTIME_CONFIG.json']:secret_paths.append(Path(json.loads((E/cfg).read_text())['password_file']))
patterns=[]
for p in secret_paths:
 if p.exists():
  value=p.read_bytes().strip()
  if value:patterns.extend([value,hashlib.sha256(value).hexdigest().encode()])
maxpat=max(map(len,patterns),default=1);hits=[];files_count=0;bytes_count=0
for base,dirs,names in os.walk(E,followlinks=False):
 dirs[:]=sorted(dirs)
 for name in sorted(names):
  p=Path(base)/name
  if p.is_symlink() or not p.is_file():continue
  files_count+=1;bytes_count+=p.stat().st_size;tail=b''
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):
    part=tail+b
    if any(v in part for v in patterns):hits.append(str(p.relative_to(E)));break
    tail=part[-maxpat:]
  # Product and review source ZIPs receive a decompressed member check too.
  if p.suffix=='.zip':
   with zipfile.ZipFile(p) as z:
    for i in z.infolist():
     with z.open(i) as f:
      tail=b''
      for b in iter(lambda:f.read(1048576),b''):
       part=tail+b
       if any(v in part for v in patterns):hits.append(str(p.relative_to(E))+'::'+i.filename);break
       tail=part[-maxpat:]
assert not hits, 'CREDENTIAL_SCAN_HIT_PATHS_ONLY:'+repr(hits)
(E/'reports/CREDENTIAL_SCAN.json').write_text(json.dumps(dict(status='PASS_NO_KNOWN_REAL_CREDENTIAL_OR_INDIVIDUAL_HASH_HITS',files=files_count,bytes=bytes_count,known_secret_file_count=len(secret_paths),zip_members_decompressed=True,secret_values_or_individual_hashes_archived=False,paths_retained_for_internal_traceability=True),indent=2)+'\n')
# Self-boundary is explicit and limited to the two terminal index files.
excluded={'DELIVERY_MANIFEST.json','DELIVERY_MANIFEST_SHA256.txt'};files={};links=[];special=[]
for base,dirs,names in os.walk(E,followlinks=False):
 dirs[:]=sorted(dirs)
 for name in list(dirs):
  p=Path(base)/name
  if p.is_symlink():
   s=p.lstat();links.append(dict(path=str(p.relative_to(E)),target=os.readlink(p),mode=oct(s.st_mode&0o7777)));dirs.remove(name)
 for name in sorted(names):
  p=Path(base)/name;n=str(p.relative_to(E))
  if n in excluded:continue
  s=p.lstat()
  if stat.S_ISLNK(s.st_mode):links.append(dict(path=n,target=os.readlink(p),mode=oct(s.st_mode&0o7777)))
  elif stat.S_ISREG(s.st_mode):files[n]=dict(bytes=s.st_size,mode=oct(s.st_mode&0o7777),mtime_ns=s.st_mtime_ns,sha256=sha(p))
  else:special.append(n)
assert not special,'Unsealed special entries: '+repr(special)
m=dict(schema='aevora.full.g21/1.0',sealed_at=now(),self_boundary=sorted(excluded),classification='PRIVATE_MAINTAINER_NOT_PUBLIC_NOT_PARTICIPANT',files=files,links=links,bytes=sum(v['bytes'] for v in files.values()),source=json.loads((E/'FINAL_SOURCE.json').read_text()),grade='G21_CONDITIONAL',new_real_agent_runs=0)
with (E/'DELIVERY_MANIFEST.json').open('x') as f:json.dump(m,f,sort_keys=True,indent=2);f.write('\n')
with (E/'DELIVERY_MANIFEST_SHA256.txt').open('x') as f:
 for n,v in sorted(files.items()):f.write(v['sha256']+'  '+n+'\n')
 f.write(sha(E/'DELIVERY_MANIFEST.json')+'  DELIVERY_MANIFEST.json\n')
print(json.dumps(dict(status='SEALED',files=len(files),links=len(links),bytes=m['bytes'],manifest_sha256=sha(E/'DELIVERY_MANIFEST.json'),checksum_sha256=sha(E/'DELIVERY_MANIFEST_SHA256.txt'))))
