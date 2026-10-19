from audit import *
import stat,hashlib,json
r=json.loads((E/'G20_FINAL_DELIVERY_RECEIPT.json').read_text());assert r['G20_STATUS']=='G20_READY_FOR_REVIEW'
assert json.loads((E/'commands/g20-build-review-bundle/receipt.json').read_text())['exit_code']==0
assert sha(Path(r['review_zip']))==r['zip_sha256']
# No writes to any sealed payload after this point; terminal verification receipts are external.
files={};links=[];total=0;special=[]
secret=[]
p=Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')
if p.is_file():secret.append(p.read_text().strip().encode())
old=BASE.parents[1];cfg=json.loads((old/'RUNTIME_CONFIG.json').read_text());p=Path(cfg['password_file'])
if p.is_file():secret.append(p.read_text().strip().encode())
secret=[x for x in secret if len(x)>7];needles=secret+[hashlib.sha256(x).hexdigest().encode() for x in secret];hits=[]
ex={'DELIVERY_MANIFEST.json','DELIVERY_MANIFEST_SHA256.txt'}
for p in sorted(E.rglob('*')):
 n=str(p.relative_to(E));s=p.lstat()
 if n in ex or stat.S_ISDIR(s.st_mode):continue
 if stat.S_ISLNK(s.st_mode):links.append({'path':n,'target':os.readlink(p),'mode':oct(s.st_mode&0o7777)});continue
 if not stat.S_ISREG(s.st_mode):special.append(n);continue
 h=hashlib.sha256();tail=b'';hit=False
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):
   h.update(b)
   if any(x in tail+b for x in needles):hit=True
   tail=(tail+b)[-512:]
 if hit:hits.append(n)
 after=p.stat();assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
 files[n]={'sha256':h.hexdigest(),'bytes':s.st_size,'mode':oct(s.st_mode&0o7777),'mtime_ns':s.st_mtime_ns};total+=s.st_size
assert not hits and not special,('SECRET_OR_SPECIAL_ENTRY_FOUND',hits,special)
write(E/'DELIVERY_MANIFEST.json',{'schema':'aevora.g20.full/1','at':now(),'G20_STATUS':'G20_READY_FOR_REVIEW','scope':'LOCAL_MAINTAINER_FULL_NOT_PUBLIC_NOT_PARTICIPANT','file_count':len(files),'bytes':total,'files':files,'links':links,'self_boundary':sorted(ex),'privacy':'Actual known Gateway/ownedDB secret values and individual hashes scanned in memory; zero hits; values/hashes not stored','terminal_verification':'Post-seal receipts live in external aevora_review_exports root; not written back to Full','authority':'Local hashes, no external notarization','stop':'G2-0_PENDING_REVIEW_NO_G2-1_NO_PUSH'})
p=E/'DELIVERY_MANIFEST_SHA256.txt';p.write_text(''.join(v['sha256']+'  '+n+'\n' for n,v in sorted(files.items()))+sha(E/'DELIVERY_MANIFEST.json')+'  DELIVERY_MANIFEST.json\n')
print(json.dumps({'status':'SEALED','G20_STATUS':'G20_READY_FOR_REVIEW','full_root':str(E),'files':len(files),'bytes':total,'links':len(links),'manifest_sha256':sha(E/'DELIVERY_MANIFEST.json'),'checksums_sha256':sha(p),'zip_sha256':r['zip_sha256'],'zip_files':r['zip_files'],'commit':r['design_commit'],'tree':r['design_tree']}))
