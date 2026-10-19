"""G20 independent stdlib read-only review-package verifier; never executes package code."""
import argparse,csv,hashlib,json,re
from pathlib import Path,PurePosixPath
import xml.etree.ElementTree as ET
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def require(b,m):
 if not b:raise ValueError(m)
def verify(root,expected):
 mf=root/'PACKAGE_MANIFEST.json';require(re.fullmatch('[0-9a-f]{64}',expected) is not None and sha(mf)==expected,'EXTERNAL_MANIFEST_SHA_MISMATCH')
 m=load(mf);files=m['files'];actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
 require(not any(p.is_symlink() for p in root.rglob('*')),'SYMLINK_REFUSED')
 require(actual==set(files)|{'PACKAGE_MANIFEST.json','SHA256SUMS.txt'},'MEMBER_SET')
 for n,d in files.items():
  pp=PurePosixPath(n);require(not pp.is_absolute() and '..' not in pp.parts and '\\' not in n,'UNSAFE_MEMBER')
  require((root/n).stat().st_size==d['bytes'] and sha(root/n)==d['sha256'],'PAYLOAD_HASH:'+n)
 sums={}
 for line in (root/'SHA256SUMS.txt').read_text().splitlines():
  h,n=line.split('  ',1);require(n not in sums,'DUPLICATE_SUM');sums[n]=h
 require(set(sums)==set(files)|{'PACKAGE_MANIFEST.json'},'SUM_SET')
 for n,h in sums.items():require(sha(root/n)==h,'CHECKSUM:'+n)
 links=list(csv.DictReader((root/'SOURCE_LINKS.csv').open()))
 for x in links:require(sha(root/x['package_path'])==x['original_sha256'],'ORIGINAL_BYTE_COPY_LINK')
 index=load(root/'design/CONTRACT_FREEZE_INDEX.json')
 require(index['new_design_files']==49 and len(index['files'])==48,'DESIGN_ASSET_COUNT')
 for n,d in index['files'].items():require(sha(root/'design'/n)==d['sha256'],'FROZEN_CONTRACT:'+n)
 identity=load(root/'receipts/TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json')
 require(identity['main_clean'] and identity['v5c1_clean'] and identity['new_clean'],'SOURCE_CLEAN')
 require(identity['main547_verified']==547 and identity['v5c1_551_verified']==551 and identity['production_source_changes']==0,'SOURCE_BOUNDARY')
 require(identity['new_head']==m['design_commit'] and identity['new_tree']==m['design_tree'],'DESIGN_GIT_IDENTITY')
 require(identity['historical_v5c1_full_files_rehashed']==28596 and identity['historical_v5c1_full_links_verified']==2544,'HISTORICAL_RECEIPT')
 require(identity['owned_probe_containers_remaining']==0 and identity['new_model_challenges']==0,'OWNED_SCOPE')
 tests=list(ET.parse(root/'checks/release-final/JUNIT.xml').getroot().iter('testcase'))
 require(len(tests)==59 and all(not list(x) for x in tests),'DESIGN_JUNIT')
 require(len({(x.get('classname'),x.get('name')) for x in tests})==59,'DUPLICATE_TEST')
 cmd=load(root/'commands/g20-final-contract-acceptance/receipt.json');require(cmd['exit_code']==0,'ACTUAL_PYTEST_EXIT')
 require(sha(root/'commands/g20-final-contract-acceptance/stdout.log')==cmd['stdout_sha256'],'PYTEST_STDOUT')
 require(sha(root/'checks/release-final/JUNIT.xml')==index['current_design_checks']['junit_sha256'],'JUNIT_FREEZE_LINK')
 probe=load(root/'probes/attempt2/RESULT.json')
 require(probe['status']=='PASS_SYNTHETIC_QUERY_AND_CONSTRAINT_SHAPES_ONLY','PROBE_SCOPE')
 require(probe['duplicate_actual_exit']==probe['mandatory_actual_exit']==1 and probe['fenced_stale_rows']==[],'PROBE_NEGATIVE')
 require((probe['multi_hop_rows'],probe['cut_rows'],probe['restored_rows'],probe['cross_tenant_rows'])==(2,1,2,0),'PROBE_INTERVENTION')
 gate=load(root/'receipts/G20_GATE_RESULTS.json')
 require(gate['G20_STATUS']=='G20_READY_FOR_REVIEW' and gate['new_native_multi_agent']=='NOT_RUN' and gate['gen2_production_implementation']=='NOT_IMPLEMENTED' and not gate['G2_1_authorized'],'DO_NOT_UPGRADE_DESIGN_TO_PRODUCT')
 return {'status':'PASS_LOCAL_REVIEW_PACKAGE_INTEGRITY','files':len(actual),'source_copy_links':len(links),'design_assets':49,'design_tests':59,'design_commit':m['design_commit'],'G20_STATUS':'G20_READY_FOR_REVIEW','product_implementation':'NOT_IMPLEMENTED','new_native_multi_agent':'NOT_RUN','inherited1897':'HISTORICAL_NOT_RERUN','eligibility':'ELIGIBILITY_UNCERTAIN','verification_executes_product_or_model':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
 try:r=verify(a.root,a.expected_manifest_sha256)
 except Exception as e:print(json.dumps({'status':'FAIL','error_type':type(e).__name__,'detail':str(e)}));raise SystemExit(1)
 print(json.dumps(r,indent=2))
