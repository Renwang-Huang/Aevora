"""Stdlib-only G21 sealed-local evidence verifier; no product/DB/model execution."""
import argparse,hashlib,json,os,stat
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def verify(root,expected):
 p=root/'DELIVERY_MANIFEST.json'
 if sha(p)!=expected:raise ValueError('EXTERNAL_FULL_MANIFEST_SHA_MISMATCH')
 m=json.loads(p.read_text());ex=set(m['self_boundary']);actual=set()
 for p in root.rglob('*'):
  if p.is_symlink() or not p.is_dir():
   n=str(p.relative_to(root))
   if n not in ex:actual.add(n)
 if actual!=set(m['files'])|{x['path'] for x in m['links']}:raise ValueError('FULL_MEMBER_SET')
 for n,d in m['files'].items():
  p=root/n;s=p.lstat()
  if not stat.S_ISREG(s.st_mode) or s.st_size!=d['bytes'] or sha(p)!=d['sha256'] or oct(s.st_mode&0o7777)!=d['mode'] or s.st_mtime_ns!=d['mtime_ns']:raise ValueError('FULL_BYTES_OR_METADATA:'+n)
 for d in m['links']:
  p=root/d['path'];s=p.lstat()
  if not p.is_symlink() or os.readlink(p)!=d['target'] or oct(s.st_mode&0o7777)!=d['mode']:raise ValueError('FULL_LINK:'+d['path'])
 checks={}
 for line in (root/'DELIVERY_MANIFEST_SHA256.txt').read_text().splitlines():
  h,n=line.split('  ',1)
  if n in checks:raise ValueError('DUPLICATE_CHECKSUM')
  checks[n]=h
 if set(checks)!=set(m['files'])|{'DELIVERY_MANIFEST.json'}:raise ValueError('CHECKSUM_SET')
 for n,h in checks.items():
  if sha(root/n)!=h:raise ValueError('CHECKSUM:'+n)
 return {'status':'PASS_FULL_BYTES_METADATA_LINKS','files':len(m['files']),'links':len(m['links']),'bytes':m['bytes'],'new_product_code_executed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
 try:r=verify(a.root,a.expected_manifest_sha256)
 except Exception as e:print(json.dumps({'status':'FAIL','error':str(e)}));raise SystemExit(1)
 print(json.dumps(r))
