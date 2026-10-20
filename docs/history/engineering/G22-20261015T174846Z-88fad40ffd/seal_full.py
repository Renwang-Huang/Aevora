"""Terminal local Full seal. Run without an in-Full recorder writing concurrently."""
from pathlib import Path
import hashlib,json,os,stat
E=Path(__file__).parent
excluded={'DELIVERY_MANIFEST.json','DELIVERY_MANIFEST_SHA256.txt'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
files={};links=[]
for p in sorted(E.rglob('*')):
 name=str(p.relative_to(E))
 if name in excluded:continue
 s=p.lstat()
 if stat.S_ISLNK(s.st_mode):links.append(dict(path=name,target=os.readlink(p),mode=oct(stat.S_IMODE(s.st_mode))))
 elif stat.S_ISREG(s.st_mode):files[name]=dict(bytes=s.st_size,sha256=sha(p),mode=oct(stat.S_IMODE(s.st_mode)),mtime_ns=s.st_mtime_ns)
 elif not stat.S_ISDIR(s.st_mode):raise ValueError('Unexpected live/special evidence member:'+name)
m=dict(version='aevora.g22.full/1',classification='PRIVATE_MAINTAINER',self_boundary=sorted(excluded),files=files,links=links,bytes=sum(x['bytes'] for x in files.values()))
(E/'DELIVERY_MANIFEST.json').write_text(json.dumps(m,sort_keys=True,indent=2)+'\n')
with (E/'DELIVERY_MANIFEST_SHA256.txt').open('w') as f:
 for name in sorted([*files,'DELIVERY_MANIFEST.json']):f.write(sha(E/name)+'  '+name+'\n')
print(json.dumps(dict(root=str(E),manifest_sha256=sha(E/'DELIVERY_MANIFEST.json'),files=len(files),links=len(links),bytes=m['bytes'])))
