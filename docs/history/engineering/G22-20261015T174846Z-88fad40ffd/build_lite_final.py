"""Internal G22 export. Explicit selection; Oracle/reference/source secrets excluded."""
from pathlib import Path
import json,hashlib,csv,gzip,re,zipfile,datetime
E=Path(__file__).parent;P=E/'worktree';O=E/'deliverables';O.mkdir(exist_ok=True)
S=O/'audit-lite-final';S.mkdir();links=[]
sha=lambda b:hashlib.sha256(b).hexdigest()

def redact(raw):
 text=raw.decode('utf8')
 text=text.replace('/home/PRIVATE_MAINTAINER/data_storage/','/HOST_DATA/').replace('/home/PRIVATE_MAINTAINER/.config/','/HOST_CONFIG/').replace('/home/PRIVATE_MAINTAINER/.codex/','/HOST_CODEX/').replace('/home/PRIVATE_MAINTAINER/','/HOST_HOME/')
 text=text.replace('127.0.0.1','OWNED_LOOPBACK').replace('localhost','OWNED_LOOPBACK')
 if '@' in text:text=re.sub(r'\b[A-Za-z0-9_.+\-]{1,64}@[A-Za-z0-9.\-]{1,253}\.[A-Za-z]{2,63}\b', 'REDACTED_EMAIL',text)
 return text.encode()
def add(src,dst,compressed=False):
 if compressed and not dst.endswith('.gz'):dst += '.gz'
 src=Path(src);original=src.read_bytes();data=gzip.decompress(original) if src.suffix=='.gz' else original
 exported=redact(data)
 transform='EXACT_BYTE_COPY' if exported==original else 'REDACTED_UTF8'
 if compressed:
  exported=gzip.compress(exported,compresslevel=6,mtime=0);transform='REDACTED_UTF8_GZIP' if redact(data)!=data or src.suffix=='.gz' else 'LOSSLESS_GZIP'
 target=S/dst;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(exported)
 links.append(dict(package_path=dst,original_path_alias=str(src.relative_to(E)) if src.is_relative_to(E) else 'WORKTREE/'+str(src.relative_to(P)),original_sha256=sha(original),export_sha256=sha(exported),transform=transform,original_uncompressed_sha256=sha(data)))
for f in sorted((E/'reports').glob('*')):
 if f.is_file() and f.suffix in ['.md','.json','.csv']:add(f,'reports/'+f.name)
for f in sorted((P/'docs/gen2/g22').glob('*')):
 if f.is_file():add(f,'docs/'+f.name)
for src,dst in [('SOURCE_DIFF.patch','SOURCE_DIFF.patch'),('FINAL_SOURCE.json','receipts/FINAL_SOURCE.json'),('RUNTIME_VERSIONS.json','receipts/RUNTIME_VERSIONS.json'),('package_verify.py','verify.py'),('TASKBOOK.md','TASKBOOK.md')]:add(E/src,dst)
add(E/'reports/TEST_IDENTITY_CHECK.json','receipts/TEST_IDENTITY_CHECK.json')
for label,src,command in [('inherited','06_regression/inherited-1897-final/JUNIT.xml','inherited-1897-final'),('gen2','06_regression/gen2-108-acceptance/JUNIT.xml','gen2-108-acceptance'),('g22','06_regression/acceptance-host-58/JUNIT.xml','acceptance-host-58'),('design','06_regression/DESIGN_ENTRY_86.xml','contract-86')]:
 add(E/src,'junit/'+label+'.xml');add(E/'commands'/command/'receipt.json','receipts/'+label+'-command.json')
# All command exits/times/stdout/stderr hashes; original bulky logs stay Full.
for f in sorted((E/'commands').glob('*/receipt.json')):add(f,'commands/'+f.parent.name+'.json')
for f in sorted((E/'06_regression/acceptance-host-58/cypher').glob('*.jsonl')):add(f,'raw/g22/'+f.name+'.gz',True)
for f in sorted((E/'06_regression/acceptance-host-58/artifacts/graphs').glob('*.json')):add(f,'graphs/'+f.name+'.gz',True)
for f in sorted((E/'06_regression/acceptance-host-58/artifacts/sdk').rglob('*.jsonl')):
 add(f,'sdk/'+str(f.relative_to(E/'06_regression/acceptance-host-58/artifacts/sdk'))+'.gz',True)
for folder in ['outage-recovery','outage-recovery-saved']:
 for f in sorted((E/'04_security'/folder).glob('*')):
  if f.is_file() and f.suffix in ['.json','.gz']:add(f,'recovery/'+folder+'/'+f.name,compressed=f.suffix=='.gz')
for folder in ['fair-old-20','fair-current-20','fair-host-pins-20','semantic-scale-seed','semantic-scale-acceptance','query-probe','scale-uninstrumented']:
 for f in sorted((E/'05_performance'/folder).glob('*.json')):
  if f.name=='REGISTRY.json':continue
  add(f,'performance/'+folder+'/'+f.name,compressed=f.stat().st_size>1000000)
add(E/'05_performance/semantic-scale-acceptance/RESULT.json','scale/RESULT.json')
add(E/'05_performance/semantic-scale-acceptance/RAW_CYPHER.jsonl.gz','raw/scale-operations.jsonl.gz',True)
# Fresh real Host Outcome evidence; never export the source archive, candidate
# app/answer/manifest or reference patch. Independent Oracle outputs are data.
cases=json.loads((E/'01_admission/final-cases/CASES.json').read_text())
for case in cases['cases']:
 root=Path(case['root']);base='host-outcomes/'+case['run_id']
 add(root/'evaluation_report.json',base+'/evaluation_report.json')
 add(root/'artifacts/junit.xml',base+'/junit.xml')
 for f in sorted((root/'artifacts').glob('oracle*.json')):add(f,base+'/oracle/'+f.name)
add(E/'05_benchmark/cli/summary.json','benchmark/summary.json')
add(E/'05_release/clean-smoke-final/RESULT.json','product/RESULT.json')
for f in sorted((E/'05_release/clean-smoke-final').glob('*.jsonl')):add(f,'product/'+f.name+'.gz',True)
# Original first red/failed JUnit are retained; no rewritten historical grades.
for f in sorted(E.glob('host-*.xml')):add(f,'first-failures/'+f.name)
readme='''# Aevora G22 Audit-Lite

INTERNAL_MAINTAINER_REVIEW. Not Public or Participant material. This export never executes product/DB/model code. Full retains original bytes, private truth, immutable pins and all failed attempts. This package excludes Oracle implementation, private manifests, reference patches, credentials, Git object stores, venvs and RDB volumes.

1. Compare the ZIP SHA256 from the external delivery receipt.
2. Extract into a fresh directory (no pre-existing links), run a trusted copy of verify.py with --expected-manifest-sha256 from that receipt.
3. SOURCE_LINKS.csv joins every original Full file SHA to exported SHA/transform. Host paths, loopback addresses and email are aliases. Redacted raw SDK/Cypher are review views: original delivery/frame/document SHA refer to original Full bytes, not transformed wire bytes. XML identities/counts are checked, while the exact old/new identity comparison was made on original unredacted Full.
4. Local hashes are not third-party attestation. Synthetic capacity records are not Agent grades. Native-v2 positive/causal value/AOF unsaved power-loss remain unverified or limited as stated.

Actual source commit and tree are in receipts/FINAL_SOURCE.json. Full manifest pin and this ZIP pin are joined by the external final receipt; there is no circular self-pinning Full SHA inside this ZIP.
'''
(S/'README.md').write_text(readme)
(S/'REDACTION_POLICY.json').write_text(json.dumps(dict(version='HOST_ALIAS_UTF8_V1',personal_host_paths='ALIASED',internal_loopback_addresses='ALIASED',email_addresses='REDACTED',original_hashes='PRESERVED',wire_hashes='ORIGINAL_FULL_BYTES_NOT_TRANSFORMED_VIEW',oracle_implementation='EXCLUDED',private_manifest='EXCLUDED',reference_patch='EXCLUDED',credentials='EXCLUDED'),indent=2))
with (S/'SOURCE_LINKS.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(links[0]));w.writeheader();w.writerows(links)
source=json.loads((E/'FINAL_SOURCE.json').read_text())
files={str(f.relative_to(S)):dict(bytes=f.stat().st_size,sha256=sha(f.read_bytes())) for f in sorted(S.rglob('*')) if f.is_file()}
m=dict(version='aevora.g22.audit/1',classification='INTERNAL_MAINTAINER_REVIEW',commit=source['head'],tree=source['tree'],files=files)
(S/'PACKAGE_MANIFEST.json').write_text(json.dumps(m,sort_keys=True,indent=2)+'\n')
with (S/'SHA256SUMS.txt').open('w') as f:
 for n in sorted([*files,'PACKAGE_MANIFEST.json']):f.write(sha((S/n).read_bytes())+'  '+n+'\n')
zip_path=O/('aevora-g22-audit-lite-'+E.name+'-final.zip')
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in sorted(S.rglob('*')):
  if f.is_file():
   info=zipfile.ZipInfo(str(f.relative_to(S)),date_time=(2026,10,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,f.read_bytes())
receipt=dict(zip=str(zip_path),zip_sha256=sha(zip_path.read_bytes()),bytes=zip_path.stat().st_size,files=len(list(S.rglob('*'))),regular_files=len(files)+2,manifest_sha256=sha((S/'PACKAGE_MANIFEST.json').read_bytes()),commit=source['head'],tree=source['tree'])
(O/'LITE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
