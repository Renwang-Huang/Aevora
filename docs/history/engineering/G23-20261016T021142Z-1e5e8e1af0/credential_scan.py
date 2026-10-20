"""Exact live credential scan; no secret or individual credential digest output."""
from pathlib import Path
import hashlib,json,base64,sys,os,gzip,zipfile,time
E=Path(__file__).parent
paths=[Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key'),*[Path(json.loads((E/n).read_text())['password_file']) for n in ['RUNTIME_CONFIG.json','RUNTIME_LIVE_CONFIG.json','RUNTIME_REGRESSION_CONFIG.json','RUNTIME_RECOVERY_CONFIG.json']]]
paths.extend([Path('/home/PRIVATE_MAINTAINER/.config/aevora/g23-audit-encryption-1e5e8e1af0/retired-db-secret'),Path('/home/PRIVATE_MAINTAINER/.config/aevora/g23-audit-encryption-1e5e8e1af0/archive-aes.key')])
patterns=set()
for p in paths:
 raw=p.read_bytes().strip()
 assert len(raw)>=16
 patterns.update([raw,hashlib.sha256(raw).hexdigest().encode(),base64.b64encode(raw)])
maxlen=max(map(len,patterns));findings=[];files=0;size=0
for p in E.rglob('*'):
 if p.is_symlink() or not p.is_file():continue
 if p.name in {'CREDENTIAL_SCAN.json'}:continue
 files+=1;size+=p.stat().st_size
 with p.open('rb') as f:
  tail=b''
  while True:
   b=f.read(1048576)
   if not b:break
   data=tail+b
   if any(x in data for x in patterns):findings.append(str(p.relative_to(E)));break
   tail=data[-maxlen:]
 # ZIP members are checked decoded, including the lossless-gzip raw streams.
 if p.suffix=='.zip':
  with zipfile.ZipFile(p) as z:
   for n in z.namelist():
    b=z.read(n)
    if n.endswith('.gz'):b=gzip.decompress(b)
    if any(x in b for x in patterns):findings.append(str(p.relative_to(E))+'::'+n)
result=dict(status='PASS_NO_MATCH' if not findings else 'FAIL',regular_files_checked=files,bytes_checked=size,exact_secret_and_sha256_and_base64=True,credential_values_or_individual_hashes_recorded=False,findings=findings,at=time.time())
out=Path(sys.argv[1]);out.write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(bool(findings))
