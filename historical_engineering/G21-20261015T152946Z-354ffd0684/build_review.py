"""Owned internal audit export. Exact-byte copies or explicit lossless gzip links; not public release."""
from audit import *
import gzip,csv,shutil,zipfile,stat
S=E/'deliverables/review-stage';S.mkdir(parents=True,exist_ok=False)
links=[]
def copy(src,dst,compress=False):
 src=Path(src);out=S/dst;out.parent.mkdir(parents=True,exist_ok=True)
 raw=src.read_bytes()
 if compress:
  with out.open('xb') as f:
   with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(raw)
 else:out.write_bytes(raw)
 links.append(dict(package_path=dst,original_path=str(src),original_sha256=sha(src),export_sha256=sha(out),transform='LOSSLESS_GZIP' if compress else 'EXACT_BYTE_COPY'))
for f in sorted((E/'reports').glob('*')):
 if f.is_file():copy(f,'reports/'+f.name)
copy(E/'reports/TEST_IDENTITY_CHECK.json','receipts/TEST_IDENTITY_CHECK.json')
copy(E/'FINAL_SOURCE.json','receipts/FINAL_SOURCE.json')
copy(E/'05_regression/inherited-acceptance/JUNIT.xml','junit/inherited.xml')
copy(E/'05_regression/gen2-acceptance-final/JUNIT.xml','junit/gen2.xml')
copy(E/'05_regression/POSTCOMMIT_CONTRACT_JUNIT.xml','junit/contracts.xml')
copy(E/'commands/inherited-final-acceptance/receipt.json','receipts/inherited-command.json')
copy(E/'commands/gen2-final-acceptance/receipt.json','receipts/gen2-command.json')
# Original failed developer JUnit and all command receipts/logs are retained.
for f in sorted(E.glob('*.xml')):copy(f,'failed_and_intermediate_junit/'+f.name)
for f in sorted((E/'05_regression').glob('*/JUNIT.xml')):
 if f.parent.name not in {'inherited-acceptance','gen2-acceptance-final'}:copy(f,'failed_and_intermediate_junit/'+f.parent.name+'.xml')
for f in sorted((E/'commands').rglob('*')):
 if f.is_file():copy(f,'commands/'+str(f.relative_to(E/'commands')))
# Current real native Cypher and raw official SDK envelopes. No private Oracle/Reference source.
for f in sorted((E/'05_regression/gen2-acceptance-final/SDK_RAW').rglob('*')):
 if f.is_file():
  rel=str(f.relative_to(E/'05_regression/gen2-acceptance-final/SDK_RAW'))
  copy(f,'sdk/'+rel+('.gz' if f.suffix=='.jsonl' else ''),compress=f.suffix=='.jsonl')
copy(E/'05_regression/gen2-acceptance-final/RAW_CYPHER.jsonl','queries/gen2-RAW_CYPHER.jsonl.gz',True)
for f in sorted((E/'05_graph_accepted').iterdir()):
 if f.is_file():copy(f,'graph/'+f.name+('.gz' if f.suffix=='.jsonl' else ''),compress=f.suffix=='.jsonl')
for f in [E/'RUNTIME_VERSIONS.json',E/'CONFIG.json',E/'RUNTIME_CONFIG.json',E/'TASKBOOK.md',E/'COMMAND_LOG.jsonl',E/'SOURCE_DIFF.patch',E/'SOURCE_DIFFSTAT.txt']:
 copy(f,'receipts/'+f.name)
for f in sorted((E/'00_baseline').glob('*.json')):copy(f,'baseline/'+f.name)
for f in sorted((E/'research').glob('*')):
 if f.is_file():copy(f,'research/'+f.name)
copy(E/'05_benchmark/cli/summary.json','benchmark/summary.json')
copy(E/'05_release/public-final-build/RESULT.json','public-build/RESULT.json')
copy(E/'05_release/public-final-build/PUBLIC_SELECTION.json','public-build/PUBLIC_SELECTION.json')
copy(E/'05_release/clean-smoke-final/RESULT.json','public-build/CLEAN_RESULT.json')
# Only changed source bytes; old maintainer truth, Git objects and RDB never exported.
changed=subprocess.check_output(['git','diff','--name-only','a54d9972aba2adb77a09667a8b656c63e089264f','HEAD'],cwd=P,text=True).splitlines()
for n in changed:
 require=not (n.startswith(('app/','benchmark/','evaluator/','integrations/','tests/')))
 if not require:raise RuntimeError('Unexpected private/business diff')
 copy(P/n,'source/'+n)
copy(E/'package_verify.py','verify.py')
(S/'README.md').write_text('''# G21 internal audit package\n\nMAINTAINER_REVIEW, not public/Participant input. Verify the externally supplied ZIP SHA before extraction, then use an independently trusted copy of the stdlib verifier with the externally supplied PACKAGE_MANIFEST SHA. No product/DB/model is executed by verification. Exact source links and original failed JUnit/command outputs are retained. Raw final SDK/Cypher streams may be losslessly gzip-compressed with explicit original SHA links. Local paths, non-secret IDs and required source hashes remain for traceability; this is secret-safe internal review, not full anonymization. Private Oracle/reference source, Git objects, DB credentials and RDB are not members. Synthetic graph outcomes are not new Agent or Oracle grades. Read reports/G21_IMPLEMENTATION_REPORT.md and G21_FAILURE_LEDGER.json first.\n''')
with (S/'SOURCE_LINKS.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['package_path','original_path','original_sha256','export_sha256','transform']);w.writeheader();w.writerows(links)
m=dict(schema='aevora.audit.g21/1.0',classification='INTERNAL_MAINTAINER_REVIEW_NOT_PUBLIC_NOT_PARTICIPANT',commit=json.loads((E/'FINAL_SOURCE.json').read_text())['head'],tree=json.loads((E/'FINAL_SOURCE.json').read_text())['tree'],files={str(f.relative_to(S)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(S.rglob('*')) if f.is_file()})
write(S/'PACKAGE_MANIFEST.json',m)
with (S/'SHA256SUMS.txt').open('x') as f:
 for n,v in sorted(m['files'].items()):f.write(v['sha256']+'  '+n+'\n')
 f.write(sha(S/'PACKAGE_MANIFEST.json')+'  PACKAGE_MANIFEST.json\n')
def archive(path):
 with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for f in sorted(S.rglob('*')):
   if f.is_file():
    info=zipfile.ZipInfo(str(f.relative_to(S)),date_time=(1980,1,1,0,0,0));info.external_attr=(stat.S_IFREG|0o644)<<16
    z.writestr(info,f.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
zip_path=E/'deliverables'/('aevora-g21-audit-lite-'+E.name+'.zip');repeat=E/'deliverables/repeat.zip';archive(zip_path);archive(repeat);assert sha(zip_path)==sha(repeat)
write(E/'deliverables/LITE_BUILD_RECEIPT.json',dict(zip=str(zip_path),sha256=sha(zip_path),manifest_sha256=sha(S/'PACKAGE_MANIFEST.json'),files=len(m['files'])+2,bytes=zip_path.stat().st_size,deterministic_repeat=True))
print((E/'deliverables/LITE_BUILD_RECEIPT.json').read_text())
