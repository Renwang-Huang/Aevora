from audit import *
import csv,zipfile,shutil,stat,re
R=E/'deliverables';S=R/'review_package';S.mkdir();links=[]

def copy(p,n):
 assert p.is_file() and not p.is_symlink();q=S/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 links.append({'source_path':str(p),'original_sha256':sha(p),'package_path':n,'bytes':p.stat().st_size})
D=P/'docs/gen2/g20'
for p in sorted(D.rglob('*')):
 if p.is_file():copy(p,'design/'+str(p.relative_to(D)))
for n in ['BASELINE_RECEIPT.json','TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json','G20_GATE_RESULTS.json','FAILURE_LEDGER.json','G20_FINAL_REVIEW_REPORT.md','RISKS_AND_OPEN_DECISIONS.md','COMMAND_LOG.jsonl','G20_DESIGN_PATCH.diff','TASKBOOK_AS_RECEIVED.md','SOURCE_ENTRYPOINT_MAP.csv','AS_IS_TO_GEN2_DELTA.csv','HACKATHON_CONTRIBUTION_MATRIX.csv','GEN2_GATES_AND_DEPENDENCIES.csv','CLAIM_TO_EVIDENCE_PLAN.csv']:
 copy(E/n,'receipts/'+n)
for folder in ['commands','checks','probes']:
 for p in sorted((E/folder).rglob('*')):
  if p.is_file() and p.suffix in ['.json','.jsonl','.log','.xml'] and 'db-data' not in p.parts:copy(p,str(p.relative_to(E)))
for n in ['SYMBOL_AND_IMPORT_INDEX.json','FILE_SYMBOL_SUMMARY.csv','ACTUAL_READONLY_RUNTIME.json','V5C1_ACTUAL_MCP_SCHEMAS.json','DESIGN_REVIEW_CORRECTIONS.json','CSV_STYLE_CORRECTION.json','FINAL_CONTRIBUTION_SCOPE.json']:
 copy(E/'source_audit'/n,'source_audit/'+n)
for p in (E/'research').glob('*.json'):copy(p,'research/'+p.name)
for n in ['RAW_JUNIT.xml','REGRESSION_IDENTITY.json','STRICT_IDENTITY_RECHECK.json','FINAL_RUNTIME_VERSIONS.json']:
 copy(E/'historical_receipts'/n,'historical/'+n)
copy(E/'review_verify.py','review_verify.py')
with (S/'SOURCE_LINKS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(links[0]),lineterminator='\n');w.writeheader();w.writerows(links)
(S/'README.md').write_text('''# Aevora G2-0 maintainer review package\n\nArchitecture/contract candidate only. Start receipts/G20_FINAL_REVIEW_REPORT.md and design/README.md.59 current tests validate design artifacts;1897 is historical and not rerun. Probe outcomes are synthetic query shapes, NOT real Agent or Oracle results. Gen2 product/NativeMulti NOT_IMPLEMENTED/NOT_RUN. No G2-1 authorization. This is MAINTAINER_REVIEW, not Participant input or public release. Contains absolute maintainer audit paths and private source SYMBOL names; no private Oracle/reference source, credentials, raw database or old native conversations.\n\nUse separately trusted review_verify.py and externally pinned ZIP/manifest SHA. Verifier only uses stdlib; it reads hashes/JSON/JUnit and does not execute product, model or DB code. Original-source links are byte-copy hashes, not third-party attestation.\n''')
# Known credential values/hashes only in memory; no individual secret hashes recorded.
needles=[]
secret=Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')
if secret.is_file():needles.append(secret.read_text().strip().encode())
oldcfg=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/V5C1-20261015T054437Z-fb77b23eff/RUNTIME_CONFIG.json')
if oldcfg.is_file():
 f=Path(json.loads(oldcfg.read_text())['password_file'])
 if f.is_file():needles.append(f.read_text().strip().encode())
needles=[n for n in needles if len(n)>7];needles += [hashlib.sha256(n).hexdigest().encode() for n in list(needles)]
hits=[]
for p in S.rglob('*'):
 if not p.is_file():continue
 n=str(p.relative_to(S));data=p.read_bytes()
 if any(x in data for x in needles):hits.append({'path':n,'kind':'ACTUAL_SECRET_OR_INDIVIDUAL_HASH'})
 if set(Path(n).parts)&{'hidden_tests','reference_patches','private_manifests','.git'} or p.suffix in ['.rdb','.sqlite','.db','.key','.pem']:hits.append({'path':n,'kind':'PRIVATE_PAYLOAD_MEMBER'})
assert not hits,hits
write(E/'deliverables/PRIVACY_SCAN.json',{'status':'PASS_ACTUAL_SECRET_AND_MEMBER_SCAN','files':sum(p.is_file() for p in S.rglob('*')),'actual_secret_values_or_individual_hashes_stored':False,'hits':hits,'classification':'MAINTAINER_REVIEW_NOT_PUBLIC_OR_DEIDENTIFIED','limits':['Private source symbol names and maintainer absolute paths intentionally retained for audit','Unknown encoded secrets not established absent']})
files={str(p.relative_to(S)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(S.rglob('*')) if p.is_file()}
identity=json.loads((E/'TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json').read_text())
write(S/'PACKAGE_MANIFEST.json',{'schema':'aevora.g20.review/1','design_commit':identity['new_head'],'design_tree':identity['new_tree'],'files':files,'self_boundary':['PACKAGE_MANIFEST.json','SHA256SUMS.txt'],'classification':'MAINTAINER_REVIEW_NOT_PARTICIPANT_OR_PUBLIC_RELEASE'})
sums={n:d['sha256'] for n,d in files.items()};sums['PACKAGE_MANIFEST.json']=sha(S/'PACKAGE_MANIFEST.json');(S/'SHA256SUMS.txt').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(sums.items())))
mh=sha(S/'PACKAGE_MANIFEST.json')
assert record('g20-review-stage-verify',['python3',E/'review_verify.py',S,'--expected-manifest-sha256',mh])==0
z=R/('aevora-g20-review-'+C['id']+'.zip')
def zipout(p):
 with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zip:
  for q in sorted(S.rglob('*')):
   if q.is_file():
    info=zipfile.ZipInfo(str(q.relative_to(S)),(2026,10,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100600<<16;zip.writestr(info,q.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
zipout(z);zipout(R/'repeat.zip');assert sha(z)==sha(R/'repeat.zip')
T=R/'extracted_verification';T.mkdir()
with zipfile.ZipFile(z) as zip:
 ns=zip.namelist();assert len(ns)==len(set(ns)) and len(ns)<10000 and sum(i.file_size for i in zip.infolist())<1024*1024*1024
 for i in zip.infolist():
  n=Path(i.filename);assert not n.is_absolute() and '..' not in n.parts and not stat.S_ISLNK(i.external_attr>>16)
  q=T/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(zip.read(i))
assert record('g20-review-extracted-verify',['python3',E/'review_verify.py',T,'--expected-manifest-sha256',mh])==0
wrong=record('g20-review-wrong-manifest-negative',['python3',E/'review_verify.py',T,'--expected-manifest-sha256','0'*64]);assert wrong==1
X=R/'tampered_copy';shutil.copytree(T,X)
with (X/'README.md').open('ab') as f:f.write(b'\nACTUAL_TAMPER_NEGATIVE\n')
tamper=record('g20-review-byte-tamper-negative',['python3',E/'review_verify.py',X,'--expected-manifest-sha256',mh]);assert tamper==1
assert 'PAYLOAD_HASH:README.md' in (E/'commands/g20-review-byte-tamper-negative/stdout.log').read_text()
write(E/'G20_FINAL_DELIVERY_RECEIPT.json',{'at':now(),'G20_STATUS':'G20_READY_FOR_REVIEW','scope':'ARCHITECTURE_AND_CONTRACT_FREEZE_ONLY','worktree':str(P),'branch':identity['new_branch'],'design_commit':identity['new_head'],'design_tree':identity['new_tree'],'base':C['base_head'],'design_assets':49,'design_tests':59,'new_model_challenges':0,'gen2_production_changes':0,'inherited1897':'HISTORICAL_PASS_NOT_RERUN','new_native_multi_agent':'NOT_RUN','eligibility':'ELIGIBILITY_UNCERTAIN','review_zip':str(z),'zip_sha256':sha(z),'zip_bytes':z.stat().st_size,'zip_files':len(ns),'package_manifest_sha256':mh,'verifier_path':str(E/'review_verify.py'),'verifier_sha256':sha(E/'review_verify.py'),'source_copy_links':len(links),'stage_verify_exit':0,'extracted_verify_exit':0,'wrong_pin_negative_exit':wrong,'actual_tamper_negative_exit':tamper,'deterministic_zip_equal':True,'privacy':'PASS_MAINTAINER_REVIEW_SCOPE_NOT_PUBLIC_EXPORT','source_history_receipt_sha256':sha(E/'TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json'),'contract_freeze_index_sha256':sha(D/'CONTRACT_FREEZE_INDEX.json'),'final_report':str(E/'G20_FINAL_REVIEW_REPORT.md'),'final_report_sha256':sha(E/'G20_FINAL_REVIEW_REPORT.md'),'full_manifest_self_boundary':'Full DELIVERY_MANIFEST_SHA256.txt created after command writers close; manifest excludes its own two index files','stopped_at':'G2-0_PENDING_INDEPENDENT_REVIEW','G2_1_authorized':False})
print('G20_REVIEW_BUNDLE_PASS',sha(z),len(ns))
