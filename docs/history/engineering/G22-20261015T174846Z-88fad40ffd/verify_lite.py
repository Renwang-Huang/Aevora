from pathlib import Path
import sys,json,zipfile,hashlib,shutil,gzip,re
E=Path(__file__).parent;sys.path.insert(0,str(E));from audit import *
r=json.loads((E/'deliverables/LITE_RECEIPT.json').read_text());stage=E/'deliverables/audit-lite-final';pin=r['manifest_sha256']
assert sha(r['zip'])==r['zip_sha256']
assert record('lite-stage-verify',[sys.executable,'-B',str(E/'package_verify.py'),str(stage),'--expected-manifest-sha256',pin],cwd=E)==0
extracted=E/'deliverables/lite-extracted';extracted.mkdir()
with zipfile.ZipFile(r['zip']) as z:
 for n in z.namelist():
  p=Path(n);assert not p.is_absolute() and '..' not in p.parts
 z.extractall(extracted)
assert record('lite-extracted-verify',[sys.executable,'-B',str(E/'package_verify.py'),str(extracted),'--expected-manifest-sha256',pin],cwd=E)==0
assert record('lite-wrong-pin',[sys.executable,'-B',str(E/'package_verify.py'),str(extracted),'--expected-manifest-sha256','0'*64],cwd=E)==1
tampered=E/'deliverables/lite-tampered';shutil.copytree(extracted,tampered)
with (tampered/'README.md').open('ab') as f:f.write(b'\nACTUAL_PAYLOAD_TAMPER_NEGATIVE_CONTROL\n')
assert record('lite-byte-tamper',[sys.executable,'-B',str(E/'package_verify.py'),str(tampered),'--expected-manifest-sha256',pin],cwd=E)==1
# Every exported text/gzip is checked for the exact personal paths and internal
# addresses this policy redacts. No source-private implementation is selected.
violations=[]
for p in stage.rglob('*'):
 if not p.is_file():continue
 data=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
 if any(token in data for token in [b'/home/PRIVATE_MAINTAINER',b'127.0.0.1',b'localhost']):violations.append(str(p.relative_to(stage)))
assert not violations,violations
write(E/'reports/LITE_EXPORT_ACCEPTANCE.json',dict(status='PASS',stage=0,extracted=0,wrong_pin=1,actual_byte_tamper=1,personal_path_address_hits=violations,files=r['regular_files'],zip_sha256=r['zip_sha256']))
print('Lite independent verification, actual tamper and alias checks passed')
