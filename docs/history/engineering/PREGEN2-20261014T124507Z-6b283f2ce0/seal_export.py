"""Private Full manifest and bounded Lite export; all original raw failures retained."""
from audit import *
import hashlib,zipfile,stat,csv,random,shutil
# Known values/solehashes stay in RAM. No authfile/secret material is copied.
secret_paths=[Path(json.loads((E/'RUNTIME_CONFIG.json').read_text())['password_file']),Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')]
old=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch/orderflow_incident_lab/aevora_validation/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef')
for p in [old/'CONFIG.json',old/'g5/fresh-user-01/CONFIG.json']:secret_paths.append(Path(json.loads(p.read_text())['password_file']))
needles=[]
for p in secret_paths:
 s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077
 b=p.read_bytes().strip();assert len(b)>16;h=hashlib.sha256(b);needles += [b,h.digest(),h.hexdigest().encode(),h.hexdigest().upper().encode()]
def secret_hits(p):
 tail=b'';overlap=max(map(len,needles))-1
 with p.open('rb') as f:
  while chunk:=f.read(1024*1024):
   part=tail+chunk
   if any(n in part for n in needles):return True
   tail=part[-overlap:]
 return False
files=[];hits=[];bytecount=0
for base,dirs,names in os.walk(E,followlinks=False):
 dirs[:]=[n for n in dirs if not (Path(base)/n).is_symlink() and not str(Path(base)/n).startswith(str(E/'lite'))]
 for n in names:
  p=Path(base)/n
  if not stat.S_ISREG(p.lstat().st_mode):continue
  files.append(p);bytecount+=p.stat().st_size
  if secret_hits(p):hits.append(str(p.relative_to(E)))
write(E/'07_audit/FULL_KNOWN_SECRET_SCAN.json',{'status':'PASS' if not hits else 'BLOCKED_SECRET_MATCH','at':now(),'ordinary_files_scanned':len(files),'bytes_scanned':bytecount,'known_secret_classes':len(secret_paths),'known_value_or_individual_hash_hits':hits,'values_and_individual_secret_hashes_emitted':False,'coverage':'All current ordinary Full/evidence files streaming; does not decode compressedGitobjects/unknown secrets; public image layers separately scanned'})
assert not hits,'Known secret matches; stop export without exposing values'
run_seals=[]
for label in ['preflight','s1','s2']:
 s=json.loads((E/'06_live_agent'/label/'SUMMARY.json').read_text());r=E/'06_live_agent'/label/'runs'/s['run_id'];m=json.loads((r/'run_evidence_manifest.json').read_text())
 mismatches=[n for n,h in m['files'].items() if sha(r/n)!=h];assert not mismatches
 run_seals.append({'label':label,'run_id':r.name,'seal_sha256':sha(r/'run_evidence_manifest.json'),'files_checked':len(m['files']),'status':'PASS_ORIGINAL_UNCHANGED'})
write(E/'07_audit/ORIGINAL_NATIVE_SEAL_VERIFICATION.json',{'status':'PASS','at':now(),'runs':run_seals,'postmortem_did_not_mutate_original':True})
manifest=json.loads((E/'07_audit/00_EXECUTION_MANIFEST.json').read_text());manifest['gates']['V6']='PASS_SOURCE_HISTORY_CLEANUP_RAW_SEAL_CHECK';(E/'07_audit/00_EXECUTION_MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
# Full terminal seal excludes derived Lite and the explicitly post-seal receipts.
excluded={'private_full/FULL_MANIFEST.sha256','private_full/FULL_MANIFEST.json','07_audit/FINAL_DELIVERY_RECEIPT.json','07_audit/AUDIT_LITE_VALIDATION_REPORT.md','07_audit/AUDIT_LITE_VALIDATION_RESULT.json','07_audit/V6_RESULT.json'}
ordinary={};links=[]
for base,dirs,names in os.walk(E,followlinks=False):
 for d in list(dirs):
  p=Path(base)/d
  if p.is_symlink():links.append({'path':str(p.relative_to(E)),'target':os.readlink(p)});dirs.remove(d)
 dirs[:]=[n for n in dirs if not str(Path(base)/n).startswith(str(E/'lite'))]
 for n in names:
  p=Path(base)/n;rel=str(p.relative_to(E))
  if rel in excluded:continue
  info=p.lstat()
  if stat.S_ISLNK(info.st_mode):links.append({'path':rel,'target':os.readlink(p)});continue
  if not stat.S_ISREG(info.st_mode):raise ValueError('Special entry in Full: '+rel)
  ordinary[rel]={'sha256':sha(p),'bytes':info.st_size,'mode':oct(stat.S_IMODE(info.st_mode))}
with (E/'private_full/FULL_MANIFEST.sha256').open('x') as f:
 for rel,row in sorted(ordinary.items()):f.write(row['sha256']+'  '+rel+'\n')
write(E/'private_full/FULL_MANIFEST.json',{'at':now(),'kind':'PRIVATE_FULL_AUDIT','root':str(E),'files':ordinary,'links':links,'ordinary_files':len(ordinary),'bytes':sum(x['bytes'] for x in ordinary.values()),'postseal_excluded':sorted(excluded),'lite_excluded':True,'immutability':'Local protected hashpin; not third-party attestation','source_head':C['head'],'source_tree':C['tree'],'model_sessions':3,'live_agent':'INCOMPLETE','admission':'PRE-GEN2 CONDITIONAL'})
fullsha=sha(E/'private_full/FULL_MANIFEST.sha256');jsonsha=sha(E/'private_full/FULL_MANIFEST.json')
# Lite documents may discuss private architecture but include no private source,
# Oracle implementation/reference patch/fullrollout/admin tool implementation.
lite=E/'lite/package';lite.mkdir(mode=0o700)
selection=['07_audit/FULL_VALIDATION_REPORT.md','07_audit/NETWORK_CHALLENGE_REPORT.md','07_audit/REGRESSION_1836_IDENTITY_REPORT.md','07_audit/BENCHMARK_ORACLE_AND_CLI_REPORT.md','07_audit/FALKORDB_AND_TRUSTED_FEEDBACK_REPORT.md','07_audit/MCP_CONSOLE_RELEASE_BOUNDARY_REPORT.md','07_audit/CURRENT_ARCHITECTURE_MAP.md','07_audit/SOURCE_AND_TRUST_BOUNDARY_AUDIT.md','07_audit/ENTRYPOINT_DEPENDENCY_GRAPH.mmd','07_audit/LIMITATIONS_AND_UNKNOWN.md','07_audit/LIMITATIONS_MATRIX.csv','07_audit/NEXT_CHAT_README.md','07_audit/NOT_INCLUDED.md','07_audit/00_EXECUTION_MANIFEST.json','07_audit/RUN_PROVENANCE_MATRIX.csv','07_audit/FULL_KNOWN_SECRET_SCAN.json','07_audit/ORIGINAL_NATIVE_SEAL_VERIFICATION.json','02_regression/expected_test_ids.txt','02_regression/actual_test_ids.txt','02_regression/id_diff.json','02_regression/regression_summary.json','02_regression/junit_full.xml','03_benchmark/cli_contract_15.csv','03_benchmark/oracle_positive_negative_matrix.csv','05_product/PACKAGE_REPEATABILITY.json','05_product/PUBLIC_RELEASE_SCAN.json','05_product/EDITOR_RESULT.json','06_live_agent/provider_preflight.json','06_live_agent/session_manifest.json','06_live_agent/native_agent_lineage.json','06_live_agent/V5_RESULT.json','06_live_agent/session2_inheritance_proof.json','06_live_agent/when_why_three_state.csv','06_live_agent/graph_edge_negative_controls.csv','06_live_agent/participant_patch.sha256']
for rel in selection:
 p=lite/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(E/rel,p)
# Source-normalized event indices are safe bounded facts with rawline SHA pointers.
for rel in ['06_live_agent/typed_events_sanitized.jsonl','06_live_agent/mcp_request_response_timeline.jsonl']:
 p=lite/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(E/rel,p)
for n in ['01-activity-natural-origin.png','05-live-workers-abstain.png','11-live-empty-graph.png']:
 src=E/'05_product/public_browser_retry2/browser'/n;p=lite/'screens'/n;p.parent.mkdir(exist_ok=True);shutil.copyfile(src,p)
for n in ['conflict.png','withdrawn.png','real-edge-cut.png','real-edge-restored.png']:shutil.copyfile(E/'05_product/browser_supplement'/n,lite/'screens'/n)
write(lite/'FULL_POINTER.json',{'root':str(E),'manifest_sha256':fullsha,'manifest_json_sha256':jsonsha,'manifest_relative_path':'private_full/FULL_MANIFEST.sha256','private_full_not_public':True,'root_mode':'0700','postseal_terminal_receipts_excluded':True})
verifier="""# Standalone stdlib, no model/DB/candidate execution. Run from a trusted copy.
import json,hashlib,pathlib,sys
root=pathlib.Path(sys.argv[1]);m=json.loads((root/'LITE_MANIFEST.json').read_text())
for rel,row in m['files'].items():
 p=root/rel
 if pathlib.PurePosixPath(rel).is_absolute() or '..' in pathlib.PurePosixPath(rel).parts or p.is_symlink():raise SystemExit('unsafe path')
 if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise SystemExit('digest mismatch '+rel)
print('PASS',len(m['files']),'Lite file digests; this is integrity, not new runtime execution')
"""
(lite/'verify_lite.py').write_text(verifier)
assert not any(secret_hits(p) for p in lite.rglob('*') if p.is_file())
lm={str(p.relative_to(lite)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in lite.rglob('*') if p.is_file()}
write(lite/'LITE_MANIFEST.json',{'files':lm,'kind':'SANITIZED_AUDIT_LITE','source_head':C['head'],'full_manifest_sha256':fullsha,'scope':'Hash/ID/derivedindices/rawgreenJUnit/publicscreens; no private source/Oracle/ref/credential/fullrawrollout','live_agent':'INCOMPLETE'})
z=E/'lite'/('aevora-pregen2-audit-lite-'+C['run_id']+'.zip')
with zipfile.ZipFile(z,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
 for p in sorted(lite.rglob('*')):
  if p.is_file():
   info=zipfile.ZipInfo(str(p.relative_to(lite)),date_time=(1980,1,1,0,0,0));info.external_attr=(stat.S_IFREG|0o600)<<16;archive.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
# Actual independent unpack validation. Never execute raw material from package.
unpack=E/'lite/unpacked-verification';unpack.mkdir(mode=0o700)
with zipfile.ZipFile(z) as archive:
 for info in archive.infolist():
  path=Path(info.filename);assert not path.is_absolute() and '..' not in path.parts and stat.S_IFMT(info.external_attr>>16)!=stat.S_IFLNK
 archive.extractall(unpack)
assert not any(secret_hits(p) for p in unpack.rglob('*') if p.is_file())
checks=json.loads((unpack/'LITE_MANIFEST.json').read_text());assert all(sha(unpack/rel)==row['sha256'] for rel,row in checks['files'].items())
for p in unpack.rglob('*'):
 if p.is_file():
  assert not set(p.relative_to(unpack).parts)&{'hidden_tests','reference_patches','private_manifests','.git','owned_runtime','official_rollouts_private'}
assert all(sha(E/rel)==row['sha256'] for rel,row in ordinary.items())
result={'status':'PASS','at':now(),'lite_zip':str(z),'lite_zip_sha256':sha(z),'lite_zip_bytes':z.stat().st_size,'unpacked_file_count':len(checks['files']),'secret_matches':0,'forbidden_path_matches':0,'source_bytes_not_included':True,'full_file_digests_rechecked':len(ordinary),'full_manifest_sha256':fullsha,'full_manifest_json_sha256':jsonsha,'coverage':'Finite known4secret classes and namedprivatepath/ordinary member rules; unknownsecretabsence not promised','live_agent':'INCOMPLETE','native':'SINGLE','causal_benefit':'UNKNOWN','source_head':C['head'],'source_tree':C['tree'],'provisional_admission':'PRE-GEN2 CONDITIONAL'}
write(E/'07_audit/AUDIT_LITE_VALIDATION_RESULT.json',result)
(E/'07_audit/AUDIT_LITE_VALIDATION_REPORT.md').write_text('# Actual Full/Lite integrity check\n\nPASS: actual ZIP unpack, '+str(len(checks['files']))+'fileSHA checks,4knownsecret/solehashclasses scan with0hits,privatepath0hits, Full '+str(len(ordinary))+'hashes rechecked. ZIP SHA '+result['lite_zip_sha256']+'. Full localprotectedhashpin, noexternalattestation; finite scan scope only. Native loop remainsINCOMPLETE.\n')
write(E/'07_audit/V6_RESULT.json',{'status':'PASS','at':now(),'source_history_cleanup':'PASS','original_native_seals':'PASS_UNCHANGED','full_integrity':'PASS','lite_unpack_integrity':'PASS','known_secret_scans':'PASS_FINITE','source_code_changed':False,'historical_scores_changed':False,'remote_push':False})
write(E/'07_audit/FINAL_DELIVERY_RECEIPT.json',{**result,'gates':{'V0':'PASS','V1':'PASS_STATIC_SCOPE','V2':'PASS','V3':'PASS_WITH_RETAINED_COLLECTION_FAILURES','V4':'PASS_WITH_PUBLIC_STAGING_CONDITION','V5':'CONDITIONAL_PASS_INCOMPLETE','V6':'PASS'},'full_root':str(E),'reports_root':str(E/'07_audit'),'new_sessions':3,'new_upstream_forwarded':40,'original_native_exits':[1,1,1],'original_s1_evaluation':'NOT_RUN','diagnostic_untouched_actor_oracle':'28PASS','native_s2_inheritance':'NOT_PROVEN','host_controlled_publication':'PASS_NOT_NATURAL_PROPOSAL','gen2_code_changed':False,'git_push':False,'stopped':True,'final_admission_authority':'USER_AND_INDEPENDENT_REVIEW'})
print(json.dumps({'status':'PASS_INTEGRITY','out':str(E),'lite':str(z),'sha256':sha(z),'full_files':len(ordinary),'live_agent':'INCOMPLETE','admission':'PRE-GEN2 CONDITIONAL'}),flush=True)
