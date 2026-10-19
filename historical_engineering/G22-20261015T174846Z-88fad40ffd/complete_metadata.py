from pathlib import Path
import json,hashlib,subprocess,csv,gzip
E=Path(__file__).parent;P=E/'worktree';R=E/'reports';D=P/'docs/gen2/g22'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Verify original business/evaluator/reference/test source bytes via baseline Git.
base='387352df3d5358d5f0ed8eadc784ef7170843ee0'
changed=subprocess.check_output(['git','diff','--name-only',base],cwd=P,text=True).splitlines()
protected=['app/','benchmark/','evaluator/','integrations/','tests/']
assert not any(any(n.startswith(prefix) for prefix in protected) for n in changed)
(R/'PROTECTED_SOURCE_CHECK.json').write_text(json.dumps(dict(base=base,changed=changed,protected_prefixes=protected,protected_changes=[],status='PASS'),indent=2))
files=subprocess.check_output(['git','ls-files','-z'],cwd=P).split(b'\0')
manifest={n.decode():sha(P/n.decode()) for n in files if n and (P/n.decode()).is_file() and not (P/n.decode()).is_symlink()}
(E/'SOURCE_MANIFEST_SHA256.json').write_text(json.dumps(manifest,sort_keys=True,indent=2))
# One observed output interval includes DB validation + socket send, not an
# isolated distributed TOCTOU bound. Original exact events stay in Full.
interval=[];delivered=0;source_files=[]
for f in (E/'06_regression/acceptance-host-58/artifacts/sdk').rglob('events.jsonl'):
 source_files.append(dict(file=str(f.relative_to(E)),sha256=sha(f)))
 for line in f.read_text().splitlines():
  event=json.loads(line)
  if event.get('category')=='V2_RESPONSE_DELIVERED':
   delivered+=1
   if 'check_to_send_seconds' in event:interval.append(event['check_to_send_seconds'])
(R/'AUTHORIZATION_BOUNDARY_MEASUREMENTS.json').write_text(json.dumps(dict(events=source_files,delivered=delivered,samples=len(interval),min=min(interval) if interval else None,max=max(interval) if interval else None,scope='real DB-check plus complete socket send; upper bound, not atomic distributed revocation',external_db_network_race_remains=True,already_delivered_unretractable=True),indent=2))
pins=json.loads((E/'05_performance/fair-host-pins-20/RESULT.json').read_text())
for root in [D,R]:
 p=root/'G22_PERFORMANCE_AND_SCALE.md';s=p.read_text();s+='\n## Durable Host pin path\n\nSame exact64×8 graph,20 additional production lookup-only registry samples: observed p50 %.6fs, p95 %.6fs, max %.6fs. No permission cache; full witnesses still equal the frozen baseline.\n'%(pins['observed_p50'],pins['observed_p95'],pins['max']);p.write_text(s)
 p=root/'G22_IMPLEMENTATION_REPORT.md';s=p.read_text();s+='\n## Product repeat build\n\nFirst two wheel files differed only in ZIP timestamps; all member payloads were identical. The failure is retained in BUILD_REPEAT_INITIAL.json. Two further builds used the standard SOURCE_DATE_EPOCH from the actual implementation commit timestamp: source ZIP and both wheels match byte-for-byte (BUILD_REPEAT_FINAL.json). No source timestamp, Git date, historic evidence or score was rewritten. The clean17-check install tested the same exact wheel member bytes in an isolated product-only namespace.\n';p.write_text(s)
(R/'RESEARCH_REFERENCES.json').write_text(json.dumps(dict(primary_sources=[dict(url='https://docs.falkordb.com/design/concurrency',use='single query atomicity/writer ordering; pinned4.20.4 separately dynamically tested'),dict(url='https://github.com/FalkorDB/docs/pull/398',use='mature documented atomicity model'),dict(url='https://github.com/FalkorDB/falkordb-py',use='reuse official pinned1.7.1 transport'),dict(url='https://reproducible-builds.org/docs/source-date-epoch/',use='standard deterministic ZIP timestamp environment; no Git date change')],new_runtime_or_database_implementation=False),indent=2))
# Explicit remaining limitations; no unobserved state is silently PASS.
limits=[('Native-v2 positive source','NOT_RUN','G23 required; reused native archive validator and fake-origin rejection are tested'),('Proposing actor thread','UNAVAILABLE','exact actor not inferred from parent or nearest time'),('Causal benefit','UNKNOWN','no Graph/Raw/NoMemory experiment'),('Unsaved crash/power loss','UNVERIFIED','last-SAVE RPO; actual initial unsaved-stage loss retained'),('AOF139','KNOWN_LIMITATION','not changed or destructively retested'),('Hostile kernel/UID','PARTIAL','existing shared-kernel fence, no VM claim'),('DB/network atomic revocation','NOT_GUARANTEED','fresh final check/local lock plus measured interval; delivered bytes unretractable'),('Artifact-before extractor breadth','BOUNDED','unsupported facts stay PENDING, no after-to-before promotion'),('Wide governance fanout','BOUNDED','prepared8MiB, final pins16384, scope/candidate/path limits; oversized write rejected before activation'),('First prototype source bytes','UNAVAILABLE','first two constructor failures before source snapshots; raw errors/JUnit preserved'),('Independent attestation','NOT_CLAIMED','local SHA/OS authority, same disk failure domain')]
with (R/'LIMITATIONS_MATRIX.csv').open('w') as f:w=csv.writer(f);w.writerow(['subject','status','evidence_limit']);w.writerows(limits)
print('protection, source pins, authorization telemetry and limits complete')
