"""Explicit internal G23 export. Run only after reports/source are final."""
from pathlib import Path
import json,hashlib,csv,gzip,re,zipfile,sys
E=Path(__file__).parent;P=E/'worktree';O=E/(sys.argv[1] if len(sys.argv)>1 else 'deliverables');O.mkdir(exist_ok=True)
S=O/'audit-lite';S.mkdir();links=[]
sha=lambda b:hashlib.sha256(b).hexdigest()
def redact(raw):
 text=raw.decode('utf8')
 for a,b in [('/home/PRIVATE_MAINTAINER/data_storage/','/HOST_DATA/'),('/home/PRIVATE_MAINTAINER/.config/','/HOST_CONFIG/'),('/home/PRIVATE_MAINTAINER/.codex/','/HOST_CODEX/'),('/home/PRIVATE_MAINTAINER/','/HOST_HOME/'),('api.renwang-huang.top','OWNED_GATEWAY_ENDPOINT'),('127.0.0.1','OWNED_LOOPBACK')]:text=text.replace(a,b)
 if '@' in text:text=re.sub(r'\b[A-Za-z0-9_.+\-]{1,64}@[A-Za-z0-9.\-]{1,253}\.[A-Za-z]{2,63}\b','REDACTED_EMAIL',text)
 return text.encode()
def add(src,dst,compressed=False):
 src=Path(src);original=src.read_bytes();data=redact(original);transform='EXACT_BYTE_COPY' if data==original else 'REDACTED_UTF8'
 if compressed:
  dst+='.gz';data=gzip.compress(data,compresslevel=6,mtime=0);transform='LOSSLESS_GZIP' if redact(original)==original else 'REDACTED_UTF8_GZIP'
 target=S/dst;target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('xb') as f:f.write(data)
 links.append(dict(package_path=dst,original_path_alias=str(src.relative_to(E)),original_sha256=sha(original),export_sha256=sha(data),transform=transform))
for f in sorted((E/'reports').glob('*')):
 if f.is_file() and f.suffix in {'.md','.json','.csv'}:add(f,'reports/'+f.name)
for f in sorted((P/'docs/gen2/g23').glob('*')):
 if f.is_file():add(f,'docs/'+f.name)
for name,dest in [('source/SOURCE_IDENTITY.json','source/SOURCE_IDENTITY.json'),('source/SOURCE_DIFF.patch','source/SOURCE_DIFF.patch'),('RUNTIME_VERSIONS.json','receipts/RUNTIME_VERSIONS.json'),('package_verify.py','verify.py'),('EXPERIMENT_REGISTRATION.json','EXPERIMENT_REGISTRATION.json')]:add(E/name,dest)
add(E/'10_regression_final/benchmark-cli-15/summary.json','regression/CLI15.json')
add(E/'10_regression_final/EXACT_IDENTITY_RECEIPT.json','regression/EXACT_IDENTITY_RECEIPT.json')
for label,src,command in [('inherited','inherited-1897/JUNIT.xml','epoch4-inherited-1897'),('gen2','gen2-108/JUNIT.xml','epoch4-gen2-108'),('g22','host58-exact-root/JUNIT.xml','epoch4-host58-exact-root'),('contracts','CONTRACT86.xml','epoch4-contracts-86')]:
 add(E/'10_regression_final'/src,'junit/'+label+'.xml');add(E/'commands'/command/'receipt.json','receipts/'+label+'-command.json')
add(E/'10_regression_final/host58-new46/JUNIT.xml','junit/g23-plus58.xml')
# Preserve every original model attempt, official own rollout and exact tool stream.
roots=[*sorted((E/'04_live').glob('*/runs/*')),*sorted((E/'01_native/preflight/runs').glob('*'))]
for r in roots:
 if not r.is_dir():continue
 prefix='native/'+r.name
 for n in ['runtime_metadata.json','codex_events.jsonl','agent_trace.jsonl','native_agent_trace.jsonl','native_rollout_summary.json','gateway_transport_events.jsonl','aevora_mcp_events.jsonl','evaluation_report.json','run_evidence_manifest.json','submission.diff','input_seal.json']:
  if (r/n).is_file():add(r/n,prefix+'/'+n,compressed=(r/n).stat().st_size>1000000)
 for f in sorted((r/'artifacts/native_rollouts').rglob('*.jsonl')):add(f,prefix+'/official/'+str(f.relative_to(r/'artifacts/native_rollouts')),True)
 for f in sorted((r/'artifacts').glob('oracle*.json')):add(f,prefix+'/oracle/'+f.name,True)
 if (r/'artifacts/junit.xml').is_file():add(r/'artifacts/junit.xml',prefix+'/junit.xml')
 if (r/'sealed_public_inputs/AEVORA_MCP_CONTRACT.json').is_file():add(r/'sealed_public_inputs/AEVORA_MCP_CONTRACT.json',prefix+'/public-tool-contract.json')
for folder in ['04_live','05_security','05_performance','05_controls']:
 for f in sorted((E/folder).rglob('*')):
  if not f.is_file() or f.is_symlink() or f.suffix not in {'.json','.md','.csv'}:continue
  rel=f.relative_to(E);parts=rel.parts
  if any(x in {'runs','private_host_pins','source_archive','frozen_fixture','baseline_core','db-data','state','venv'} for x in parts):continue
  if f.name in {'RECOVERED_LAST_SAVE_GRAPH.json','PRIVATE_REGISTRY.json'}:continue
  if f.name.endswith('BOOTSTRAP.json') or 'registry' in f.name.lower() or f.name=='HOST_V2_CONFIG.json':continue
  add(f,'evidence/'+str(rel),f.stat().st_size>1000000)
add(E/'09_release_final/clean-smoke-final/RESULT.json','product/CLEAN_INSTALL_17.json')
for f in sorted((E/'commands').glob('*/receipt.json')):add(f,'commands/'+f.parent.name+'.json')
for f in sorted((E/'07_regression_epoch2').rglob('JUNIT.xml')):add(f,'failures/epoch2/'+str(f.relative_to(E/'07_regression_epoch2')))
for f in sorted((E/'02_source').glob('*.xml')):add(f,'failures-or-contracts/'+f.name)
for f in sorted((E/'02_source/predicate-red').glob('JUNIT.xml')):add(f,'failures/predicate-red.xml')
(S/'README.md').write_text('''# Aevora G23 Audit-Lite

INTERNAL_MAINTAINER_REVIEW, not Public or Participant material. Original Full retains all bytes, private truth, pins and failed attempts. This ZIP excludes Oracle implementation, reference patches, private manifests, credentials, Git stores, venvs, RDB and mutable Codex state. Actual Agent patches and independent Oracle output data are included for review.

Use the external ZIP SHA and manifest SHA, extract into a fresh directory and run a trusted copy of verify.py. SOURCE_LINKS.csv joins original Full file SHA to exported SHA and transformation. Raw event/document/frame hashes refer to original Full archived bytes; aliases/redaction/gzip change exported bytes. No full Gateway HTTP request/response body is invented: transport metadata and official native/MCP streams are retained where captured. Missing fields stay UNAVAILABLE.

Local hashes are not third-party attestation; controlled graph tests are not Agent grades. Causal benefit remains UNKNOWN. Every original ERROR, invalid proposal, engine outage and later diagnostic retains its own identity. Source/Runtime/Oracle/Publication/Transfer grades remain distinct.
''')
with (S/'SOURCE_LINKS.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(links[0]));w.writeheader();w.writerows(links)
source=json.loads((E/'source/SOURCE_IDENTITY.json').read_text());files={str(f.relative_to(S)):{'bytes':f.stat().st_size,'sha256':sha(f.read_bytes())} for f in sorted(S.rglob('*')) if f.is_file()}
(S/'PACKAGE_MANIFEST.json').write_text(json.dumps(dict(version='aevora.g23.audit/1',classification='INTERNAL_MAINTAINER_REVIEW',commit=source['head'],tree=source['tree'],files=files),sort_keys=True,indent=2)+'\n')
with (S/'SHA256SUMS.txt').open('w') as f:
 for n in sorted([*files,'PACKAGE_MANIFEST.json']):f.write(sha((S/n).read_bytes())+'  '+n+'\n')
zpath=O/('aevora-g23-audit-lite-'+E.name+'.zip')
with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in sorted(S.rglob('*')):
  if f.is_file():
   info=zipfile.ZipInfo(str(f.relative_to(S)),date_time=(2026,10,16,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,f.read_bytes())
receipt=dict(zip=str(zpath),zip_sha256=sha(zpath.read_bytes()),bytes=zpath.stat().st_size,regular_files=len(files)+2,manifest_sha256=sha((S/'PACKAGE_MANIFEST.json').read_bytes()),commit=source['head'],tree=source['tree'])
(O/'LITE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
