"""Audit-only redaction of newly captured credential-bearing failures.
Original bytes retained AES256-GCM encrypted; key never enters Full/Lite.
"""
from pathlib import Path
import json,hashlib,os,base64,zipfile,io,time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
E=Path(__file__).parent;X=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_review_exports')/E.name/'preseal/extracted';K=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('g23-audit-encryption-'+E.name.split('-')[-1]);K.mkdir(mode=0o700);key=os.urandom(32);fd=os.open(K/'archive-aes.key',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,key);os.close(fd)
enc=E/'sensitive_originals_encrypted';enc.mkdir(mode=0o700);patterns={}
for cfg in ['RUNTIME_CONFIG.json','RUNTIME_LIVE_CONFIG.json','RUNTIME_REGRESSION_CONFIG.json','RUNTIME_RECOVERY_CONFIG.json']:
 raw=Path(json.loads((E/cfg).read_text())['password_file']).read_bytes().strip()
 for p,form in [(raw,'VALUE'),(hashlib.sha256(raw).hexdigest().encode(),'INDIVIDUAL_SHA256'),(base64.b64encode(raw),'BASE64')]:patterns[p]=(cfg,form)
raw=Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key').read_bytes().strip()
for p,form in [(raw,'VALUE'),(hashlib.sha256(raw).hexdigest().encode(),'INDIVIDUAL_SHA256'),(base64.b64encode(raw),'BASE64')]:patterns[p]=('PROJECT_GATEWAY',form)
sha=lambda b:hashlib.sha256(b).hexdigest();records=[]
def clean(b):
 categories=[]
 for value,cat in patterns.items():
  if value in b:categories.append(cat);b=b.replace(value,b'REDACTED_PROJECT_CREDENTIAL')
 return b,categories
def preserve(path,raw,alias,categories):
 n=str(len(records))+'.aesgcm';nonce=os.urandom(12);cipher=nonce+AESGCM(key).encrypt(nonce,raw,alias.encode());p=enc/n;p.write_bytes(cipher);p.chmod(0o600)
 rec=dict(path_alias=alias,original_artifact_sha256=sha(raw),encrypted_original_file=str(p.relative_to(E)),encrypted_sha256=sha(cipher),algorithm='AES256_GCM',key_location='EXTERNAL_HOST_ONLY_NOT_ARCHIVED',associated_data=alias,credential_classes=categories);records.append(rec);return rec
# Only new, unsealed artifacts and the preflight external extraction. All older
# frozen sources and archives are outside these roots.
for root,scope in [(E,'FULL'),(X,'EXTERNAL_PRESEAL_EXTRACTION')]:
 for p in sorted(root.rglob('*')):
  if p.is_symlink() or not p.is_file() or enc in p.parents:continue
  alias=(str(p.relative_to(E)) if root==E else scope+'/'+str(p.relative_to(root)))
  if p.suffix=='.zip':
   raw=p.read_bytes();changed=False;members=[];cats=[]
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    for item in z.infolist():
     b=z.read(item.filename);c,found=clean(b);changed|=bool(found);cats+=found;members.append((item,c))
   if changed:
    rec=preserve(p,raw,alias,cats)
    # This is an INVALIDATED preseal package, not silently a new accepted ZIP.
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
     for item,b in members:z.writestr(item,b)
    p.write_bytes(buf.getvalue());rec['sanitized_sha256']=sha(buf.getvalue());rec['state']='PRESEAL_PACKAGE_INVALIDATED_DO_NOT_USE_OLD_RECEIPT'
   continue
  raw=p.read_bytes();c,cats=clean(raw)
  if cats:
   rec=preserve(p,raw,alias,cats);p.write_bytes(c);rec['sanitized_sha256']=sha(c);rec['state']='SANITIZED_DERIVATIVE_ORIGINAL_ENCRYPTED'
assert records,'No actual sensitive artifact found'
result=dict(status='REDACTED_NEW_CAPTURE_ONLY',at=time.time(),original_plaintext_retained=False,encrypted_originals_retained=True,key_in_archive=False,records=records,preserved_semantics='Original failures/exits/test identities unchanged; credential substrings only. Original command capture SHA values still identify decryptable originals, sanitized file SHA separate.')
(E/'reports/G23_CAPTURE_REDACTION_RECEIPT.json').write_text(json.dumps(result,indent=2))
inv=dict(status='INVALIDATED_CREDENTIAL_LEAK_FOUND_BEFORE_FINAL_DELIVERY',at=time.time(),original_zip_receipt='LITE_RECEIPT.json preserved as original, now refers to encrypted original bytes',redaction_receipt_sha256=sha((E/'reports/G23_CAPTURE_REDACTION_RECEIPT.json').read_bytes()),use_only='Final deliverables/ new package after clean scan; this preseal is not accepted')
(E/'deliverables_preseal/INVALIDATED.json').write_text(json.dumps(inv,indent=2));(X.parent/'INVALIDATED.json').write_text(json.dumps(inv,indent=2));print(json.dumps({'redacted_artifacts':len(records),'classes':sorted({x for r in records for x in r['credential_classes']}),'plaintext_credentials_or_digests_printed':False}))
