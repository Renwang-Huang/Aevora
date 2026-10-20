"""Read-only stdlib audit verifier. Based on G23 payload/manifest verification.
This checks byte integrity, selected identities and typed receipts, not external
attestation, a new model experiment or truth of historical Oracle assertions.
"""
import argparse,csv,hashlib,json,stat,sys
from pathlib import Path,PurePosixPath
import xml.etree.ElementTree as ET

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def need(ok,name):
 if not ok:raise ValueError(name)
def verify(root,pin):
 need(not root.is_symlink(),'ROOT_LINK');m=root/'PACKAGE_MANIFEST.json';need(sha(m)==pin,'EXTERNAL_MANIFEST_PIN');data=json.loads(m.read_text())
 actual=set()
 for p in root.rglob('*'):
  need(not p.is_symlink(),'LINK')
  if p.is_file():need(stat.S_ISREG(p.stat().st_mode),'SPECIAL');actual.add(str(p.relative_to(root)))
 need(actual==set(data['files'])|{'PACKAGE_MANIFEST.json','SHA256SUMS.txt'},'MEMBER_SET')
 for name,row in data['files'].items():
  p=PurePosixPath(name);need(not p.is_absolute() and '..' not in p.parts and '\\' not in name,'UNSAFE_PATH');p=root/name
  need(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'PAYLOAD:'+name)
 sums={}
 for line in (root/'SHA256SUMS.txt').read_text().splitlines():
  h,n=line.split('  ',1);need(n not in sums,'DUPLICATE_SUM');sums[n]=h
 need(set(sums)==set(data['files'])|{'PACKAGE_MANIFEST.json'},'SUM_SET')
 for n,h in sums.items():need(sha(root/n)==h,'CHECKSUM:'+n)
 for row in csv.DictReader((root/'SOURCE_LINKS.csv').open()):
  need(sha(root/row['package_path'])==row['export_sha256'],'EXPORT_LINK')
  if row['transform']=='EXACT_BYTE_COPY':need(row['original_sha256']==row['export_sha256'],'ORIGINAL_BYTE_COPY')
 all_ids=set()
 for label,count in [('inherited',1897),('graph-v2',108),('host-native',104),('contracts',86),('new',32)]:
  rows=ET.parse(root/'junit'/f'{label}.xml').findall('.//testcase');ids={(r.get('classname'),r.get('name')) for r in rows}
  need(len(rows)==len(ids)==count,'JUNIT_IDENTITY:'+label);need(all(not any(c.tag in {'failure','error','skipped'} for c in r) for r in rows),'JUNIT_NONPASS:'+label);need(not all_ids&ids,'DUPLICATE_SUITE_IDENTITY');all_ids|=ids
 need(len(all_ids)==2227,'TOTAL_IDENTITY')
 need(json.loads((root/'receipts/PUBLIC_BOUNDARY.json').read_text())['status']=='PASS','PUBLIC_BOUNDARY')
 need(json.loads((root/'receipts/CLEAN_INSTALL_RESULT.json').read_text())['status']=='PASS','CLEAN_INSTALL')
 need(json.loads((root/'receipts/BROWSER_RESULT.json').read_text())['status']=='PASS','BROWSER_RESULT')
 need(json.loads((root/'receipts/FALKORDB_NECESSITY_RECEIPT.json').read_text())['status']=='PASS','FALKORDB_NECESSITY')
 return dict(status='PASS_LOCAL_INTEGRITY_ONLY',files=len(actual),pytest_unique_identities=2227,classification=data['classification'],model_or_database_executed=False,attestation='LOCAL_HASHES_NOT_THIRD_PARTY_PROOF')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
 try:print(json.dumps(verify(a.root,a.expected_manifest_sha256),sort_keys=True))
 except Exception as e:print(json.dumps(dict(status='FAIL',error=str(e))));raise SystemExit(1)
