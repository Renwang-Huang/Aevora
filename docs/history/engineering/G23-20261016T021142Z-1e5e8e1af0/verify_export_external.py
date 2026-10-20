"""Run after the Full seal; all receipts go OUTSIDE Full."""
from pathlib import Path,PurePosixPath
import json,subprocess,hashlib,zipfile,shutil,sys
E=Path(__file__).parent;O=Path(sys.argv[1]);O.mkdir(parents=True,exist_ok=True,mode=0o700);O.chmod(0o700)
r=json.loads((E/(sys.argv[2] if len(sys.argv)>2 else 'deliverables')/'LITE_RECEIPT.json').read_text());z=Path(r['zip']);assert hashlib.sha256(z.read_bytes()).hexdigest()==r['zip_sha256']
X=O/'extracted';X.mkdir()
with zipfile.ZipFile(z) as a:
 for i in a.infolist():
  p=PurePosixPath(i.filename);assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and not ((i.external_attr>>16)&0o170000)==0o120000
 a.extractall(X)
def run(label,args,expected):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE);(O/(label+'.stdout')).write_bytes(p.stdout);(O/(label+'.stderr')).write_bytes(p.stderr);v={'argv':list(map(str,args)),'exit':p.returncode,'expected':expected};(O/(label+'.json')).write_text(json.dumps(v,indent=2));assert p.returncode==expected,label
# Trusted verifier is copied from separately pinned maintainer source, not executed
# implicitly from arbitrary ZIP. Hashes remain local integrity assertions.
v=O/'trusted_verify.py';shutil.copyfile(E/'package_verify.py',v)
run('lite-positive',[sys.executable,str(v),str(X),'--expected-manifest-sha256',r['manifest_sha256']],0)
run('lite-wrong-manifest',[sys.executable,str(v),str(X),'--expected-manifest-sha256','0'*64],1)
p=X/'README.md';old=p.read_bytes();p.write_bytes(bytes([old[0]^1])+old[1:]);run('lite-actual-byte-tamper',[sys.executable,str(v),str(X),'--expected-manifest-sha256',r['manifest_sha256']],1);p.write_bytes(old)
run('lite-restored',[sys.executable,str(v),str(X),'--expected-manifest-sha256',r['manifest_sha256']],0)
print(json.dumps({'status':'PASS_LOCAL_INTEGRITY_AND_NEGATIVES','zip_sha256':r['zip_sha256'],'files':r['regular_files'],'external':str(O)}))
