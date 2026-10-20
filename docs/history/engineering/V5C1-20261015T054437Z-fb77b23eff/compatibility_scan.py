from audit import *
import zipfile,tarfile
out=E/'03_regression/package-scan-retry1';out.mkdir()
node=E/'owned_runtime/node'
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());needles=[]
for path in [Path(cfg['password_file']),Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')]:
 v=path.read_bytes().strip()
 if len(v)>7:needles.extend([v,__import__('hashlib').sha256(v).hexdigest().encode()])
hits=[];members=[]
def inspect(name,raw):
 if any(x in Path(name).parts for x in ['evaluator','reference_patches','private_manifests','private_labels','.git']) or name.endswith(('.password','.key','auth.json')):hits.append({'path':name,'reason':'FORBIDDEN_MEMBER'})
 if any(v in raw for v in needles):hits.append({'path':name,'reason':'KNOWN_SECRET_OR_ITS_HASH'})
 members.append({'path':name,'bytes':len(raw),'sha256':__import__('hashlib').sha256(raw).hexdigest()})
for p in sorted((E/'03_regression/public-build').glob('*.zip'))+sorted((E/'03_regression/public-build/dist').iterdir()):
 if p.suffix in ('.zip','.whl'):
  with zipfile.ZipFile(p) as z:
   for n in z.namelist():
    if not n.endswith('/'):inspect(p.name+'!/'+n,z.read(n))
 else:
  with tarfile.open(p) as t:
   for m in t.getmembers():
    assert not m.issym() and not m.islnk()
    if m.isfile():inspect(p.name+'!/'+m.name,t.extractfile(m).read())
write(out/'PUBLIC_PACKAGE_MEMBER_SCAN.json',{'status':'PASS' if not hits else 'FAIL','members':members,'member_count':len(members),'hits':hits,'secret_values_and_individual_hashes':'IN_MEMORY_ONLY_NOT_ARCHIVED','local_only':True,'new_browser_tour':'NOT_RUN; unchanged Console, targeted JS/backend regression and actual package compatibility only','node_sha256':sha(node),'at':now()})
assert not hits
print('PUBLIC_MEMBERS',len(members),'PASS; CONSOLE_JS_6_SEPARATELY_VERIFIED')
