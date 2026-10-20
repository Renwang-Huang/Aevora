"""Independent stdlib G21 review verifier. Never imports/executes product code or connects DB/model."""
import argparse,json,hashlib,stat,csv,re
from pathlib import Path,PurePosixPath
import xml.etree.ElementTree as ET
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def req(b,m):
 if not b:raise ValueError(m)
def verify(root,pin):
 manifest=root/'PACKAGE_MANIFEST.json';req(sha(manifest)==pin,'EXTERNAL_MANIFEST_SHA')
 m=json.loads(manifest.read_text());actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
 req(not any(p.is_symlink() for p in root.rglob('*')),'SYMLINK')
 req(actual==set(m['files'])|{'PACKAGE_MANIFEST.json','SHA256SUMS.txt'},'MEMBER_SET')
 for n,d in m['files'].items():
  part=PurePosixPath(n);req(not part.is_absolute() and '..' not in part.parts and '\\' not in n,'UNSAFE_MEMBER')
  req((root/n).stat().st_size==d['bytes'] and sha(root/n)==d['sha256'],'PAYLOAD:'+n)
 sums={}
 for line in (root/'SHA256SUMS.txt').read_text().splitlines():
  h,n=line.split('  ',1);req(n not in sums,'DUPLICATE_SUM');sums[n]=h
 req(set(sums)==set(m['files'])|{'PACKAGE_MANIFEST.json'},'SUM_SET')
 for n,h in sums.items():req(sha(root/n)==h,'CHECKSUM:'+n)
 for label,count in [('inherited',1897),('gen2',108)]:
  cases=list(ET.parse(root/'junit'/f'{label}.xml').getroot().iter('testcase'))
  req(len(cases)==count and all(not list(c) for c in cases),'JUNIT_'+label)
  req(len({(c.get('classname'),c.get('name')) for c in cases})==count,'DUPLICATE_'+label)
  receipt=json.loads((root/'receipts'/f'{label}-command.json').read_text());req(receipt['exit']==0,'PYTEST_EXIT_'+label)
 identity=json.loads((root/'receipts/TEST_IDENTITY_CHECK.json').read_text());req(identity['original']==identity['current']==1897 and not identity['missing'] and not identity['extra'] and not identity['duplicate'],'IDENTITY')
 ledger=json.loads((root/'reports/G21_GATE_RESULTS.json').read_text());req(ledger['G22_HOST_PUBLICATION']=='NOT_RUN' and ledger['G23_NATIVE_MULTI_AGENT']=='NOT_RUN' and ledger['HISTORICAL_SOURCE_CHANGED'] is False,'BOUNDARY')
 source=json.loads((root/'receipts/FINAL_SOURCE.json').read_text());req(source['clean'] and source['head']==m['commit'] and source['tree']==m['tree'],'GIT_IDENTITY')
 for row in csv.DictReader((root/'SOURCE_LINKS.csv').open()):
  req(sha(root/row['package_path'])==row['export_sha256'],'EXPORT_LINK')
  if row['transform']=='EXACT_BYTE_COPY':req(row['export_sha256']==row['original_sha256'],'ORIGINAL_LINK')
  else:
   import gzip
   with gzip.open(root/row['package_path'],'rb') as f:
    h=hashlib.sha256()
    for b in iter(lambda:f.read(1048576),b''):h.update(b)
   req(h.hexdigest()==row['original_sha256'],'GZIP_ORIGINAL_LINK')
 return dict(status='PASS_LOCAL_INTEGRITY_ONLY',files=len(actual),commit=m['commit'],tree=m['tree'],inherited=1897,gen2=108,product_or_model_execution=False,verdict=ledger['G21_FINAL'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
 try:print(json.dumps(verify(a.root,a.expected_manifest_sha256),indent=2))
 except Exception as e:print(json.dumps({'status':'FAIL','error':str(e)}));raise SystemExit(1)
