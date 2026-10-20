from audit import *
import ast,csv,re,shutil,stat,sys,zipfile
D=E/'delivery_final';D.mkdir(exist_ok=False);F=D/'Full';F.mkdir(mode=0o700);L=D/'Audit-Lite';L.mkdir(mode=0o700)
# Mature stdlib Full verifier is reused byte-for-byte from G23.
g23=E.parent/'G23-20261016T021142Z-1e5e8e1af0'
shutil.copyfile(g23/'full_verify.py',E/'verify_full.py')
# Existing credential-pattern helper extracted without importing unrelated
# Python3.12 maintainer types into this host3.10 evidence-only collector.
source=P/'integrations/codex_trace.py';tree=ast.parse(source.read_text());names={'REDACTED','_SECRET_ASSIGNMENT','_BEARER','_API_KEY','_JWT'};nodes=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):nodes.append(node)
 if isinstance(node,ast.FunctionDef) and node.name=='redact_text':nodes.append(node)
ns={'re':re};exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(source),'exec'),ns);mature_redact=ns['redact_text']
write(E/'VERIFIER_PROVENANCE.json',dict(full_verifier_source='G23 full_verify.py',source_sha256=sha(g23/'full_verify.py'),copied_sha256=sha(E/'verify_full.py'),lite_verifier='G23 generic payload/member/SHA/source-link algorithm reused with current2227 JUnit and release receipt checks',redactor_source='integrations/codex_trace.py',redactor_source_sha256=sha(source),scope='No new business/evaluation policy or Agent runtime.'))
# Refresh index only after all completed preseal command receipts exist.
commands=[]
for p in sorted((E/'commands').glob('*/receipt.json')):
 row=json.loads(p.read_text());commands.append(dict(label=p.parent.name,receipt=str(p.relative_to(E)),receipt_sha256=sha(p),**row))
write(E/'G2_FINAL_COMMAND_INDEX.json',commands)
roots=[p for p in E.iterdir() if p.is_dir() and (re.match(r'^\d\d_',p.name) or p.name in {'source','final','commands','security-tools','regression-db-data','PUBLIC_STAGING'})]
excluded_parts={'.git','__pycache__','node_modules','.pytest_cache','.mypy_cache'}
nonregular=[]
selected=set(p for p in E.iterdir() if p.is_file() and p.suffix in {'.json','.jsonl','.md','.py','.csv','.txt'})
for root in roots:
 for p in root.rglob('*'):
  rel=p.relative_to(E)
  if set(rel.parts)&excluded_parts or 'CLEAN_CLONE' in rel.parts:continue
  info=p.lstat()
  if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
   item=dict(path=str(rel),mode=oct(info.st_mode),uid=info.st_uid,gid=info.st_gid,mtime_ns=info.st_mtime_ns,type='SYMLINK' if stat.S_ISLNK(info.st_mode) else 'SPECIAL_FILE',disposition='METADATA_ONLY_NOT_OPENED_OR_FOLLOWED')
   if stat.S_ISLNK(info.st_mode):
    target=os.readlink(p);item.update(target=target,target_text_sha256=hashlib.sha256(os.fsencode(target)).hexdigest())
   nonregular.append(item);continue
  if stat.S_ISREG(info.st_mode):selected.add(p)
known=private_values();total=0
for p in sorted(selected):
 b=p.read_bytes()
 if any(v in b for v in known):raise ValueError('Known credential detected in Full input: '+str(p.relative_to(E)))
 q=F/p.relative_to(E);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);total+=len(b)
write(F/'NONREGULAR_SOURCE_RECEIPTS.json',dict(items=nonregular,source_namespace_unchanged=True,disposition='Original link/special metadata retained; no target access, no named pipe/socket open. Original fixtures remain in owned stage.'))
(F/'FULL_LAYOUT.md').write_text('''# G2-FINAL Full evidence boundary

INTERNAL_MAINTAINER_REVIEW; never public/competition/Participant material.
This Full contains current-stage command receipts/stdout/stderr, successful and
failed regression/Benchmark archives, rejected public candidates, selected safe
public source/distributions, actual graph/MCP/browser/image evidence, recording
and reports/drivers. Historical G23 Native logs/pins and G24 assets are referenced
by original hashes and preserved in their independent prior archives; they are
not relabeled or duplicated as new runs. The stage Git stores, venv/runtime,
package caches and active Docker volume directories are retained in the owned
workspace rather than treated as portable dependencies. Intentional test symlink/FIFO/socket artifacts are represented by exact metadata
receipts and are not followed/opened. The stopped owned
regression RDB is included as private evidence, never as public demo data.

DELIVERY_MANIFEST/sha sidecar exclude themselves. Receipts for archive export and
postseal verification live outside this sealed Full. Local read-only permissions
and hashes are not third-party immutable storage or experiment attestation.
''')
# Full is terminal after this manifest. Every regular-file byte is pinned.
files={}
for p in sorted(F.rglob('*')):
 if p.is_file():
  p.chmod(0o444);s=p.stat();files[str(p.relative_to(F))]=dict(bytes=s.st_size,sha256=sha(p),mode=oct(s.st_mode&0o7777),mtime_ns=s.st_mtime_ns)
full_manifest=dict(version='aevora.g2-final.full/1',classification='INTERNAL_MAINTAINER_REVIEW',created_at=now(),files=files,links=[],bytes=sum(v['bytes'] for v in files.values()),self_boundary=['DELIVERY_MANIFEST.json','DELIVERY_MANIFEST_SHA256.txt'])
write(F/'DELIVERY_MANIFEST.json',full_manifest)
with (F/'DELIVERY_MANIFEST_SHA256.txt').open('w') as f:
 for n in sorted([*files,'DELIVERY_MANIFEST.json']):f.write(sha(F/n)+'  '+n+'\n')
for p in F.rglob('*'):
 if p.is_file():p.chmod(0o444)
for p in sorted([p for p in F.rglob('*') if p.is_dir()],reverse=True):p.chmod(0o500)
F.chmod(0o500)
write(D/'FULL_RECEIPT.json',dict(root=str(F),manifest_sha256=sha(F/'DELIVERY_MANIFEST.json'),files=len(files),bytes=full_manifest['bytes'],status='SEALED_LOCAL_READ_ONLY',classification='INTERNAL_MAINTAINER_REVIEW'))
# Portable Lite: explicit UTF-8 redaction with original/export SHA joins; raw
# sessions, private truth/pins/DB, images and browser trace ZIP remain Full-only.
links=[]
secret_strings=[x.decode('utf8') for x in known]
def cleaned(b):
 t=mature_redact(b.decode('utf8'),secret_values=secret_strings)
 for a,v in [('/home/PRIVATE_MAINTAINER/data_storage/','/HOST_DATA/'),('/home/PRIVATE_MAINTAINER/.config/','/HOST_CONFIG/'),('/home/PRIVATE_MAINTAINER/.codex/','/HOST_CODEX/'),('/home/PRIVATE_MAINTAINER/','/HOST_HOME/')]:t=t.replace(a,v)
 t=re.sub(r'\b[A-Za-z0-9_.+\-]{1,64}@[A-Za-z0-9.\-]{1,253}\.[A-Za-z]{2,63}\b','REDACTED_EMAIL',t)
 t=re.sub(r'hostname="[^"]*"','hostname="OWNED_HOST"',t)
 return t.encode()
def add(rel,dst=None,binary=False):
 src=F/rel;assert src.is_file(),rel;old=src.read_bytes();b=old if binary else cleaned(old);dst=dst or rel;q=L/dst
 assert not q.exists(),dst;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 links.append(dict(package_path=dst,original_path_alias=rel,original_sha256=hashlib.sha256(old).hexdigest(),export_sha256=hashlib.sha256(b).hexdigest(),transform='EXACT_BYTE_COPY' if old==b else 'REDACTED_UTF8'))
for rel in ['G2_FINAL_RELEASE_REPORT.md','G2_FINAL_CLAIM_TO_EVIDENCE.csv','G2_FINAL_FAILURE_LEDGER.json','G2_FINAL_PUBLIC_SAFETY_AUDIT.md','G2_FINAL_SUBMISSION_CHECKLIST.md','G2_FINAL_GIT_RECEIPT.json','FINAL_RELEASE_MANIFEST.json','PUBLIC_RELEASE_RISK_MATRIX.json','README_FINAL_DELIVERY.md']:
 add(rel,'reports/'+rel)
add('source/SOURCE_IDENTITY.json');add('source/BASELINE_PRESERVATION.json');add('source/SOURCE_DIFF.patch');add('verify_lite.py','verify.py');add('VERIFIER_PROVENANCE.json');add('G2_FINAL_COMMAND_INDEX.json','receipts/COMMAND_INDEX.json')
for label,path in [('inherited','12_release_regression/inherited-1897/JUNIT.xml'),('graph-v2','12_release_regression/graph-v2-108/JUNIT.xml'),('host-native','12_release_regression/host58-native46/JUNIT.xml'),('contracts','12_release_regression/CONTRACT86.xml'),('new','01_tests/RELEASE_NEW32.xml'),('clean-public','final/acceptance_verified/PUBLIC_JUNIT.xml')]:add(path,'junit/'+label+'.xml')
for path,dst in [('final/security/PUBLIC_BOUNDARY.json','PUBLIC_BOUNDARY.json'),('final/acceptance_verified/CLEAN_INSTALL_RESULT.json','CLEAN_INSTALL_RESULT.json'),('final/browser-framed/RESULT.json','BROWSER_RESULT.json'),('final/graph-necessity/FALKORDB_NECESSITY_RECEIPT.json','FALKORDB_NECESSITY_RECEIPT.json'),('12_release_regression/EXACT_IDENTITY_RECEIPT.json','EXACT_IDENTITY_RECEIPT.json'),('12_release_regression/benchmark-cli15/summary.json','CLI15.json'),('13_historical_review_final/HISTORICAL_SUMMARY_RECEIPT.json','HISTORICAL_SUMMARY_RECEIPT.json'),('final/image-audit/IMAGE_SCAN.json','IMAGE_SCAN.json'),('final/PUBLIC_GIT_RECEIPT.json','PUBLIC_GIT_RECEIPT.json'),('final/DEPENDENCY_LIMIT.json','DEPENDENCY_LIMIT.json'),('final/UI_RUNTIME_SOURCE_PINS.json','UI_RUNTIME_SOURCE_PINS.json'),('final/recording-source/PROVENANCE.json','RECORDING_PROVENANCE.json'),('final/video-framed/VIDEO_RECEIPT.json','VIDEO_RECEIPT.json')]:add(path,'receipts/'+dst)
for path in ['final/security/dir.json','final/security/git.json','final/graph-necessity/before.json','final/graph-necessity/disconnected.json','final/graph-necessity/after.json','final/acceptance_verified/threads-before.json','final/acceptance_verified/workers-before.json','final/acceptance_verified/unknown-before.json','final/acceptance_verified/threads-after.json']:
 add(path,'evidence/'+path.removeprefix('final/'))
for label in ['release-inherited-1897','release-graph-v2-108','release-host58-native46','release-contracts86','release-benchmark-cli15','release-new32-postfreeze','verified-safe-install-import-all-core','verified-safe-install-pip-check','verified-safe-clean-public-unit-tests','verified-safe-official-mcp-four-tools','safe-public-clean-install','public-resolved-dependency-snapshot','safe-final-gitleaks-dir','safe-final-gitleaks-git']:
 for f in ['receipt.json','stdout.log','stderr.log']:add('commands/'+label+'/'+f,'commands/'+label+'/'+f)
for c in commands:
 if c['exit']:
  for f in ['receipt.json','stdout.log','stderr.log']:add('commands/'+c['label']+'/'+f,'failures/'+c['label']+'/'+f)
add('03_regression/inherited-1897/JUNIT.xml','failures/FIRST_INHERITED.xml');add('10_security/PUBLIC_BOUNDARY.json','failures/FIRST_PUBLIC_BOUNDARY.json');add('04_browser/attempt1/RESULT.json','failures/FIRST_BROWSER.json');add('04_browser/attempt2/RESULT.json','failures/SECOND_BROWSER.json')
for p in sorted((F/'final/browser-framed').glob('*.png')):add(str(p.relative_to(F)),'screenshots/'+p.name,True)
for name in ['aevora-gen2-decision-journey.mp4','captions.srt','WALKTHROUGH.md']:add('final/video-framed/'+name,'demo/'+name,binary=name.endswith('.mp4'))
add('final/recording-source/capture_hero.mjs','demo/capture_hero.mjs');add('final/approved-build/aevora-gen2-rc1-public-source.zip','public/aevora-gen2-rc1-public-source.zip',True);add('final/approved-build/PUBLIC_SELECTION.json','public/PUBLIC_SELECTION.json');add('final/approved-build/RESULT.json','public/BUILD_RESULT.json')
for p in sorted((F/'final/approved-build/dist').iterdir()):add(str(p.relative_to(F)),'public/dist/'+p.name,True)
(L/'README.md').write_text('''# Aevora G2-FINAL Audit-Lite

INTERNAL_MAINTAINER_REVIEW. This is not the product/Participant/competition package.
Verify the ZIP SHA via the separately delivered receipt, extract safely into a
fresh directory and use a trusted external copy of verify.py with the separately
pinned PACKAGE_MANIFEST SHA. Verification is stdlib/read-only, no DB/model/code
under test. Wrong-manifest and actual-byte-tamper controls were tested externally.

SOURCE_LINKS.csv maps each selected original Full SHA to exported SHA and any
redaction. Redacted documents still refer to original raw-frame/body hashes;
those references are not expected to equal exported text hashes. Final JUnit is
included, with only host/path privacy redaction. The private Oracle code, Host
pins, grant files, RDB and raw native conversations are excluded. Prior G23 raw
Native sessions remain in their original archive; the new historical receipt
joins their285 exact line hashes without claiming new model execution. New raw
Cypher/Playwright traces/image and all first failures remain in the sealed Full.
The smaller Lite contains actual JSON observations, SDK receipts, screenshots
and real video, not fabricated substitutes for those raw files.

Only public/ sourceZIP and its dist files, plus reviewed demo assets, are product
publication candidates. Never upload the whole Audit-Lite or Full publicly.
Local hashes provide integrity, not third-party attestation or causal benefit.
''')
with (L/'SOURCE_LINKS.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(links[0]),lineterminator='\n');w.writeheader();w.writerows(links)
rows={str(p.relative_to(L)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(L.rglob('*')) if p.is_file()}
write(L/'PACKAGE_MANIFEST.json',dict(version='aevora.g2-final.audit-lite/1',classification='INTERNAL_MAINTAINER_REVIEW',commit=json.loads((E/'source/SOURCE_IDENTITY.json').read_text())['head'],files=rows))
with (L/'SHA256SUMS.txt').open('w') as f:
 for n in sorted([*rows,'PACKAGE_MANIFEST.json']):f.write(sha(L/n)+'  '+n+'\n')
write(D/'LITE_RECEIPT.json',dict(root=str(L),manifest_sha256=sha(L/'PACKAGE_MANIFEST.json'),files=len(rows)+2,bytes=sum(p.stat().st_size for p in L.rglob('*') if p.is_file()),status='READY_FOR_EXTERNAL_VERIFY',classification='INTERNAL_MAINTAINER_REVIEW'))
for label,root in [('full',F),('audit-lite',L)]:
 zpath=D/('aevora-gen2-final-'+label+'-'+E.name+'.zip')
 with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(root.rglob('*')):
   if p.is_file():z.write(p,str(p.relative_to(root)))
 write(D/(label.upper().replace('-','_')+'_ZIP_RECEIPT.json'),dict(path=str(zpath),sha256=sha(zpath),bytes=zpath.stat().st_size,files=sum(p.is_file() for p in root.rglob('*')),classification='INTERNAL_MAINTAINER_REVIEW'))
print(json.dumps(dict(status='BUILT_NOT_YET_EXTERNALLY_VERIFIED',full_files=len(files),full_bytes=full_manifest['bytes'],lite_files=len(rows)+2)))
