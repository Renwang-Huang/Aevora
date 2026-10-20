"""Independent stdlib G22 audit integrity verifier: no product/DB/model execution."""
import argparse,json,hashlib,csv,stat
from pathlib import Path,PurePosixPath
import xml.etree.ElementTree as ET

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def verify(root,pin):
 manifest=root/'PACKAGE_MANIFEST.json';require(sha(manifest)==pin,'EXTERNAL_MANIFEST_PIN')
 m=json.loads(manifest.read_text());actual=set()
 for p in root.rglob('*'):
  require(not p.is_symlink(),'SYMLINK')
  if p.is_file():actual.add(str(p.relative_to(root)))
 require(actual==set(m['files'])|{'PACKAGE_MANIFEST.json','SHA256SUMS.txt'},'MEMBER_SET')
 for name,data in m['files'].items():
  rel=PurePosixPath(name);require(not rel.is_absolute() and '..' not in rel.parts and '\\' not in name,'UNSAFE_PATH')
  require((root/name).stat().st_size==data['bytes'] and sha(root/name)==data['sha256'],'PAYLOAD:'+name)
 sums={}
 for line in (root/'SHA256SUMS.txt').read_text().splitlines():
  h,n=line.split('  ',1);require(n not in sums,'DUPLICATE_CHECKSUM');sums[n]=h
 require(set(sums)==set(m['files'])|{'PACKAGE_MANIFEST.json'},'CHECKSUM_SET')
 for name,h in sums.items():require(sha(root/name)==h,'CHECKSUM:'+name)
 for label,count in [('inherited',1897),('gen2',108),('g22',58),('design',86)]:
  rows=list(ET.parse(root/'junit'/f'{label}.xml').getroot().iter('testcase'))
  require(len(rows)==count,'TEST_COUNT_'+label)
  require(len({(r.get('classname'),r.get('name')) for r in rows})==count,'DUPLICATE_'+label)
  require(all(not any(r.find(k) is not None for k in ['failure','error','skipped']) for r in rows),'NONPASS_'+label)
  command=json.loads((root/'receipts'/f'{label}-command.json').read_text());require(command['exit']==0,'EXIT_'+label)
 identities=json.loads((root/'receipts/TEST_IDENTITY_CHECK.json').read_text())
 for label,n in [('inherited',1897),('gen2',108)]:
  v=identities[label];require(v['original']==v['current']==n and not any(v[k] for k in ['missing','extra','duplicate','nonpass']),'ORIGINAL_IDENTITIES')
 source=json.loads((root/'receipts/FINAL_SOURCE.json').read_text());require(source['clean'] and source['head']==m['commit'] and source['tree']==m['tree'],'SOURCE_IDENTITY')
 gate=json.loads((root/'reports/G22_GATE_RESULTS.json').read_text());require(gate['G23_STARTED'] is False and gate['GITHUB_PUSH'] is False and gate['HISTORICAL_SOURCE_CHANGED'] is False,'BOUNDARY')
 scale=json.loads((root/'scale/RESULT.json').read_text());require(scale['initial_nodes']==100000 and scale['initial_edges']==300000 and scale['physical_experiences']==2048 and scale['read_after_publish']=='APPLY' and scale['read_after_withdraw']=='ABSTAIN','SCALE')
 for row in csv.DictReader((root/'SOURCE_LINKS.csv').open()):
  require(sha(root/row['package_path'])==row['export_sha256'],'SOURCE_EXPORT')
  if row['transform']=='EXACT_BYTE_COPY':require(row['original_sha256']==row['export_sha256'],'ORIGINAL_COPY')
 return dict(status='PASS_LOCAL_INTEGRITY_ONLY',commit=m['commit'],tree=m['tree'],files=len(actual),inherited=2005,g22=58,product_or_model_executed=False,classification=m['classification'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
 try:print(json.dumps(verify(a.root,a.expected_manifest_sha256),indent=2))
 except Exception as error:print(json.dumps(dict(status='FAIL',error=str(error))));raise SystemExit(1)
