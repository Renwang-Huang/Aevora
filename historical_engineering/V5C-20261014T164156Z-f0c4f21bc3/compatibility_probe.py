"""Read-only public packaging scan and owned copy of official Node unit runner."""
from audit import *
import shutil,zipfile,tarfile,io
out=E/'06_regression/compatibility';out.mkdir()
node=E/'owned_runtime/node';shutil.copyfile('/usr/bin/node',node);node.chmod(0o700)
assert sha(node)==sha('/usr/bin/node') and node.stat().st_ino!=Path('/usr/bin/node').stat().st_ino
assert record('c5-owned-node-version',[node,'--version'])==0
web=E/'06_regression/public-build/source/console/web'
assert record('c5-console-js-six-existing-contracts',[node,'--test',*sorted(web.glob('*.test.mjs'))],cwd=web)==0
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());needles=[]
for path in [Path(cfg['password_file']),Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')]:
 v=path.read_bytes().strip()
 if len(v)>7:needles.extend([v,__import__('hashlib').sha256(v).hexdigest().encode()])
hits=[];members=[]
def inspect(name,raw):
 if any(x in Path(name).parts for x in ['evaluator','reference_patches','private_manifests','private_labels','.git']) or name.endswith(('.password','.key','auth.json')):hits.append({'path':name,'reason':'FORBIDDEN_MEMBER'})
 if any(v in raw for v in needles):hits.append({'path':name,'reason':'KNOWN_SECRET_OR_ITS_HASH'})
 members.append({'path':name,'bytes':len(raw),'sha256':__import__('hashlib').sha256(raw).hexdigest()})
for p in sorted((E/'06_regression/public-build').glob('*.zip'))+sorted((E/'06_regression/public-build/dist').iterdir()):
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
print('PUBLIC_MEMBERS',len(members),'PASS; CONSOLE_JS_6_PASS')
