from audit import *
import zipfile,shutil
r=json.loads((E/'deliverables/LITE_FINAL_BUILD_RECEIPT.json').read_text());pin=r['manifest_sha256'];stage=E/'deliverables/review-stage-final'
assert sha(Path(r['zip']))==r['sha256']
assert record('lite-stage-independent-verify',['python3','-B',str(E/'package_verify.py'),str(stage),'--expected-manifest-sha256',pin],cwd=E)==0
extracted=E/'deliverables/review-extracted-final';extracted.mkdir()
with zipfile.ZipFile(r['zip']) as z:
 assert len(z.namelist())==len(set(z.namelist()))==r['files']
 for n in z.namelist():
  from pathlib import PurePosixPath
  p=PurePosixPath(n);assert not p.is_absolute() and '..' not in p.parts and '\\' not in n
 z.extractall(extracted)
assert record('lite-extracted-independent-verify',['python3','-B',str(E/'package_verify.py'),str(extracted),'--expected-manifest-sha256',pin],cwd=E)==0
assert record('lite-wrong-pin-reject',['python3','-B',str(E/'package_verify.py'),str(extracted),'--expected-manifest-sha256','0'*64],cwd=E)==1
bad=E/'deliverables/review-byte-tamper-final';shutil.copytree(extracted,bad)
with (bad/'README.md').open('ab') as f:f.write(b'\nACTUAL_TAMPER_NEGATIVE\n')
assert record('lite-real-byte-tamper-reject',['python3','-B',str(E/'package_verify.py'),str(bad),'--expected-manifest-sha256',pin],cwd=E)==1
write(E/'reports/LITE_FINAL_VERIFICATION.json',dict(zip_sha256=r['sha256'],manifest_sha256=pin,files=r['files'],stage_exit=0,extracted_exit=0,wrong_pin_exit=1,actual_payload_tamper_exit=1,verifier_executes_product_or_model=False,source_oracles_included=False))
