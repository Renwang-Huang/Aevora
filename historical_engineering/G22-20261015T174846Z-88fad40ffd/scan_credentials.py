"""Known live credential scan in memory. Never records values or secret hashes."""
from pathlib import Path
import json,hashlib,gzip,zipfile,os
E=Path(__file__).parent
paths=[Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')]
for n in ['RUNTIME_CONFIG.json','PERF_RUNTIME_CONFIG.json','SCALE_RUNTIME_CONFIG.json']:paths.append(Path(json.loads((E/n).read_text())['password_file']))
patterns=[]
for p in paths:
 if p.exists():
  value=p.read_bytes().strip()
  if value:patterns += [value,hashlib.sha256(value).hexdigest().encode()]
maxn=max(map(len,patterns));hits=[];scanned=0

def check_file(stream,name):
 global scanned
 tail=b''
 for block in iter(lambda:stream.read(1048576),b''):
  data=tail+block
  if any(p in data for p in patterns):hits.append(name);break
  tail=data[-maxn:]
 scanned+=1
for p in E.rglob('*'):
 if p.is_symlink() or not p.is_file():continue
 if p.name=='CREDENTIAL_SCAN.json':continue
 name=str(p.relative_to(E))
 with p.open('rb') as f:check_file(f,name)
 if p.suffix=='.gz':
  try:
   with gzip.open(p,'rb') as f:check_file(f,name+'::DECOMPRESSED')
  except (OSError,EOFError):pass
 if p.suffix in {'.zip','.whl'}:
  with zipfile.ZipFile(p) as z:
   for member in z.infolist():
    if not member.is_dir():
     with z.open(member) as f:check_file(f,name+'::'+member.filename)
result=dict(status='PASS_NO_KNOWN_LIVE_CREDENTIAL_OR_INDIVIDUAL_HASH' if not hits else 'FAIL',files_and_members_scanned=scanned,credential_sources_available=len(paths),values_or_hashes_recorded=False,hits=hits)
(E/'reports/CREDENTIAL_SCAN.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));assert not hits
