from audit import *
import re,zipfile,tarfile
stage=E/'final/PUBLIC_STAGING';out=E/'final/security';out.mkdir(exist_ok=True)
results=[]
for mode in ['dir','git']:
 args=[E/'security-tools/gitleaks',mode,str(stage),'--redact=100','--report-format=json','--report-path',out/(mode+'.json')]
 if mode=='git':args+=['--log-opts=--all']
 results.append(dict(label=mode,exit=record('safe-final-gitleaks-'+mode,args)))
selected=json.loads((E/'final/approved-build/PUBLIC_SELECTION.json').read_text())['files']
protected={sha(p) for folder in ['evaluator/hidden_tests','evaluator/reference_patches','evaluator/private_manifests','aevora_maintainer'] for p in (P/folder).rglob('*') if p.is_file() and not p.is_symlink()}
violations=[];secret_matches=[];private_hash_matches=[];docs_errors=[];count=0
secrets=private_values()
def check(rel,b):
 global count
 count+=1
 if any(s in b for s in secrets):secret_matches.append(rel)
 if hashlib.sha256(b).hexdigest() in protected:private_hash_matches.append(rel)
 if b'/home/PRIVATE_MAINTAINER/' in b or b'/aevora_validation_runs/' in b:violations.append(dict(file=rel,error='PRIVATE_ABSOLUTE_PATH'))
for rel,row in selected.items():
 p=stage/rel
 assert not p.is_symlink() and p.is_file() and sha(p)==row['sha256']
 if re.match(r'^(app|benchmark|evaluator|integrations|aevora_maintainer|tests|runs|aevora_validation)/',rel):violations.append(dict(file=rel,error='EXCLUDED_ROOT'))
 if rel=='.env' or rel.endswith(('.password','.key','.diff')):violations.append(dict(file=rel,error='FORBIDDEN_FILE_KIND'))
 b=p.read_bytes();check(rel,b)
 if p.suffix=='.md':
  for x in re.findall(r'\]\(([^)]+)\)',b.decode()):
   target=x.split('#')[0]
   if not target or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target):continue
   dest=(p.parent/target).resolve()
   try:resolved=str(dest.relative_to(stage))
   except ValueError:resolved='OUTSIDE'
   if resolved not in selected:docs_errors.append(dict(file=rel,target=x,resolved=resolved))
for artifact in sorted((E/'final/approved-build/dist').iterdir()):
 if artifact.suffix=='.whl':
  with zipfile.ZipFile(artifact) as z:
   for n in z.namelist():check(artifact.name+'::'+n,z.read(n))
 else:
  with tarfile.open(artifact) as t:
   for m in t.getmembers():
    if m.isfile():check(artifact.name+'::'+m.name,t.extractfile(m).read())
with zipfile.ZipFile(E/'final/approved-build/aevora-gen2-rc1-public-source.zip') as z:
 assert {n.removeprefix('aevora/') for n in z.namelist()}==set(selected)
 for n in z.namelist():check('source.zip::'+n,z.read(n))
status='PASS' if not any([violations,secret_matches,private_hash_matches,docs_errors]) and all(r['exit']==0 for r in results) else 'FAIL'
v=dict(status=status,at=now(),files=len(selected),members_inspected=count,gitleaks=results,secret_matches=secret_matches,private_file_hash_matches=private_hash_matches,path_violations=violations,relative_doc_links_missing=docs_errors,protected_hash_count=len(protected),ordinary_files_only=True,scope='Explicit stage tree, full prepared public git history, wheels/sdists/sourceZIP. Known local secret byte matches; no raw credentials or individual secret hashes written.',limits=['Not a vulnerability-free proof','Legacy Host bridge definitions are public compatibility code, not production authentication implementation or pins'])
write(out/'PUBLIC_BOUNDARY.json',v);print(json.dumps(v,indent=2));raise SystemExit(0 if status=='PASS' else 1)
