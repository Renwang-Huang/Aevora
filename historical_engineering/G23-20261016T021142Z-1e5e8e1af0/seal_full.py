"""Terminal local seal. Run without an in-Full recorder after all writers stop."""
from pathlib import Path
import hashlib,json,os,stat,datetime
E=Path(__file__).parent
excluded={'DELIVERY_MANIFEST.json','DELIVERY_MANIFEST_SHA256.txt'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert not (E/'DELIVERY_MANIFEST.json').exists()
files={};links=[]
for p in sorted(E.rglob('*')):
 n=str(p.relative_to(E))
 if n in excluded:continue
 s=p.lstat()
 if p.is_symlink():links.append({'path':n,'target':os.readlink(p),'mode':oct(s.st_mode&0o7777)})
 elif stat.S_ISREG(s.st_mode):files[n]={'sha256':sha(p),'bytes':s.st_size,'mode':oct(s.st_mode&0o7777),'mtime_ns':s.st_mtime_ns}
 elif not stat.S_ISDIR(s.st_mode):raise ValueError('Unclosed special entry: '+n)
manifest={'version':'aevora.g23.full/1','classification':'PRIVATE_MAINTAINER_FULL','sealed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'self_boundary':sorted(excluded),'files':files,'links':links,'bytes':sum(x['bytes'] for x in files.values()),'immutability':'Local protected source and hashes, not external or third-party attestation'}
(E/'DELIVERY_MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
with (E/'DELIVERY_MANIFEST_SHA256.txt').open('x') as f:
 for n in sorted([*files,'DELIVERY_MANIFEST.json']):f.write(sha(E/n)+'  '+n+'\n')
print(json.dumps({'manifest_sha256':sha(E/'DELIVERY_MANIFEST.json'),'files':len(files),'links':len(links),'bytes':manifest['bytes']}))
