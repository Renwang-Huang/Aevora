"""Stdlib-only G23 audit verification. No model, DB, product or candidate execution."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,csv,xml.etree.ElementTree as ET

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def require(c,m):
 if not c:raise ValueError(m)
def verify(root,pin):
 require(not root.is_symlink(),'ROOT_LINK');manifest=root/'PACKAGE_MANIFEST.json';require(sha(manifest)==pin,'EXTERNAL_MANIFEST_PIN')
 m=json.loads(manifest.read_text());actual=set()
 for p in root.rglob('*'):
  require(not p.is_symlink(),'LINK')
  if p.is_file():actual.add(str(p.relative_to(root)))
 require(actual==set(m['files'])|{'PACKAGE_MANIFEST.json','SHA256SUMS.txt'},'MEMBER_SET')
 for n,d in m['files'].items():
  p=PurePosixPath(n);require(not p.is_absolute() and '..' not in p.parts and '\\' not in n,'UNSAFE_PATH')
  require((root/n).stat().st_size==d['bytes'] and sha(root/n)==d['sha256'],'PAYLOAD:'+n)
 sums={}
 for line in (root/'SHA256SUMS.txt').read_text().splitlines():
  h,n=line.split('  ',1);require(n not in sums,'DUPLICATE_SUM');sums[n]=h
 require(set(sums)==set(m['files'])|{'PACKAGE_MANIFEST.json'},'SUM_SET')
 for n,h in sums.items():require(sha(root/n)==h,'CHECKSUM:'+n)
 for row in csv.DictReader((root/'SOURCE_LINKS.csv').open()):
  require(sha(root/row['package_path'])==row['export_sha256'],'EXPORT_LINK')
  if row['transform']=='EXACT_BYTE_COPY':require(row['original_sha256']==row['export_sha256'],'ORIGINAL_BYTE_COPY')
 receipt=json.loads((root/'regression/EXACT_IDENTITY_RECEIPT.json').read_text())
 require(receipt['inherited']==2063 and receipt['new']==46 and receipt['contracts']==86,'INHERITED_CONTRACT')
 for label,n in [('inherited',1897),('gen2',108),('g22',58),('contracts',86)]:
  rows=ET.parse(root/'junit'/f'{label}.xml').findall('.//testcase')
  require(len(rows)==n and len({(r.get('classname'),r.get('name')) for r in rows})==n,'JUNIT_IDENTITY:'+label)
  require(all(not any(x.tag in {'failure','error','skipped'} for x in r) for r in rows),'JUNIT_NONPASS:'+label)
  c=json.loads((root/'receipts'/f'{label}-command.json').read_text());require(c['exit']==0,'COMMAND_EXIT:'+label)
 newrows=ET.parse(root/'junit/g23-plus58.xml').findall('.//testcase')
 require(len(newrows)==104 and all(not any(x.tag in {'failure','error','skipped'} for x in r) for r in newrows),'NEW_SUITE')
 observed={(r.get('classname'),r.get('name')) for r in newrows if r.get('classname','').startswith('tests.g23.')}
 require(observed=={tuple(x) for x in receipt['new_test_identities']} and len(observed)==46,'NEW_IDENTITIES')
 cli=json.loads((root/'regression/CLI15.json').read_text());require(cli['status']=='PASS' and len(cli['commands'])==15 and all(c['checks_pass'] and c['exit_code']==c['expected_exit_code'] for c in cli['commands']),'CLI15')
 product=json.loads((root/'product/CLEAN_INSTALL_17.json').read_text());require(product['status']=='PASS' and len(product['checks'])==17 and all(c['status']=='PASS' for c in product['checks']),'PUBLIC17')
 source=json.loads((root/'source/SOURCE_IDENTITY.json').read_text());require(source['clean'] and source['head']==m['commit'] and source['tree']==m['tree'],'SOURCE')
 gate=json.loads((root/'reports/G23_GATE_FINAL_STATE.json').read_text())
 require(gate['overall'] in {'G23_PASS','G23_CONDITIONAL','G23_BLOCKED'},'GRADE')
 require(gate['causal_benefit']=='UNKNOWN' and not gate['G24_STARTED'] and not gate['GITHUB_PUSH'],'SCOPE')
 return dict(status='PASS_LOCAL_INTEGRITY_ONLY',classification=m['classification'],files=len(actual),commit=m['commit'],tree=m['tree'],declared_grade=gate['overall'],historical_or_model_execution_performed=False,attestation='LOCAL_HASHES_NOT_THIRD_PARTY_PROOF')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
 try:print(json.dumps(verify(a.root,a.expected_manifest_sha256),indent=2))
 except Exception as ex:print(json.dumps({'status':'FAIL','error':str(ex)}));raise SystemExit(1)
