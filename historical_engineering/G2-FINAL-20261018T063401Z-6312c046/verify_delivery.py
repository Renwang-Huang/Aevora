from audit import *
import shutil,stat,sys,zipfile
from pathlib import PurePosixPath
D=E/'delivery_final';O=E/'audit_verification';O.mkdir(mode=0o700);full=json.loads((D/'FULL_RECEIPT.json').read_text());lite=json.loads((D/'LITE_RECEIPT.json').read_text());logs=[]
def check(label,args,expect):
 code=record(label,args,cwd=E);logs.append(dict(label=label,expected=expect,actual=code));assert code==expect,label
check('sealed-full-manifest-positive',[sys.executable,str(E/'verify_full.py'),full['root'],'--expected-manifest-sha256',full['manifest_sha256']],0)
check('sealed-full-wrong-pin-negative',[sys.executable,str(E/'verify_full.py'),full['root'],'--expected-manifest-sha256','0'*64],1)
# Check every actual ZIP member byte, without running/extracting Full content.
zfull=json.loads((D/'FULL_ZIP_RECEIPT.json').read_text());assert sha(zfull['path'])==zfull['sha256'];manifest=json.loads((Path(full['root'])/'DELIVERY_MANIFEST.json').read_text());expected=dict(manifest['files'])
for n in manifest['self_boundary']:expected[n]=dict(sha256=sha(Path(full['root'])/n),bytes=(Path(full['root'])/n).stat().st_size)
with zipfile.ZipFile(zfull['path']) as z:
 assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(expected)
 for info in z.infolist():
  p=PurePosixPath(info.filename);assert not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename and stat.S_IFMT(info.external_attr>>16)==stat.S_IFREG
  h=hashlib.sha256()
  with z.open(info) as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  assert h.hexdigest()==expected[info.filename]['sha256'] and info.file_size==expected[info.filename]['bytes']
write(O/'FULL_ZIP_MEMBER_RECHECK.json',dict(status='PASS',zip_sha256=zfull['sha256'],regular_files=len(expected),no_business_or_model_code_executed=True))
zlite=json.loads((D/'AUDIT_LITE_ZIP_RECEIPT.json').read_text());assert sha(zlite['path'])==zlite['sha256'];X=O/'lite-extracted';X.mkdir(mode=0o700)
with zipfile.ZipFile(zlite['path']) as z:
 assert len(z.namelist())==len(set(z.namelist())) and sum(i.file_size for i in z.infolist())<256*1024*1024
 for i in z.infolist():
  p=PurePosixPath(i.filename);assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and stat.S_IFMT(i.external_attr>>16)==stat.S_IFREG
 z.extractall(X)
trusted=O/'trusted_verify_lite.py';shutil.copyfile(E/'verify_lite.py',trusted)
args=[sys.executable,str(trusted),str(X),'--expected-manifest-sha256',lite['manifest_sha256']]
check('audit-lite-positive',args,0)
check('audit-lite-wrong-manifest-negative',args[:-1]+['0'*64],1)
p=X/'README.md';old=p.read_bytes();p.write_bytes(bytes([old[0]^1])+old[1:]);(O/'README_ACTUALLY_TAMPERED.bin').write_bytes(p.read_bytes())
check('audit-lite-actual-byte-tamper-negative',args,1)
p.write_bytes(old);check('audit-lite-restored-positive',args,0)
write(O/'INDEPENDENT_VERIFICATION_RESULT.json',dict(status='PASS',at=now(),checks=logs,full_zip_all_member_hashes='PASS',lite_zip_sha256=zlite['sha256'],lite_manifest_sha256=lite['manifest_sha256'],trusted_verifier_sha256=sha(trusted),scope='Read-only stdlib verification outside sealed Full, wrong external pin and actual extracted README byte tamper controls. No candidate/DB/model execution; local integrity only.'))
print('Sealed Full and Lite, all ZIP members, wrong-pin and actual-byte-tamper: PASS')
