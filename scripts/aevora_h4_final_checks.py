"""Outside sealed H4 Full: final Lite negatives, privacy and complete rehash.

Uses the unchanged separately sourced stdlib verifier. No network/model/graph or
candidate execution and no write inside Full. Failed old export attempts stay.
"""
import hashlib,json,zipfile
from pathlib import Path
from scripts.aevora_h4_audit import archive,ROOT,write,digest,record,now
from scripts.aevora_h4_delivery import patterns

def main(label):
    A=archive();E=ROOT/'aevora_validation/audit_exports'/A.name;bundle=E/('aevora-h4-audit-lite-'+label+'.zip');repeat=E/('aevora-h4-audit-lite-'+label+'-repeat.zip');verifier=E/'independent-verifier.py'
    expected=digest(bundle);assert expected==digest(repeat) and digest(verifier)==digest(ROOT/'benchmark/evidence_verify.py')
    assert record(E,'h4-independent-'+label+'-stdlib-verify',['python3','-I',str(verifier),'verify',str(bundle),'--json'])==0
    with zipfile.ZipFile(bundle) as z,zipfile.ZipFile(E/('aevora-h4-'+label+'-byte-tampered.zip'),'x') as bad:
        changed=False
        for info in z.infolist():
            data=z.read(info.filename)
            if not changed and info.filename.startswith('objects/') and data:data=data[:-1]+bytes([data[-1]^1]);changed=True
            bad.writestr(info,data)
    assert changed
    assert record(E,'h4-independent-'+label+'-byte-reject',['python3','-I',str(verifier),'verify',str(E/('aevora-h4-'+label+'-byte-tampered.zip')),'--json'])==2
    with zipfile.ZipFile(bundle) as z:
        files={i.filename:z.read(i.filename) for i in z.infolist()};index=json.loads(files['RUN_INDEX.json']);index['runs'][0]['overall_status']='PASS';files['RUN_INDEX.json']=(json.dumps(index,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    files['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items()) if name!='SHA256SUMS').encode()
    with zipfile.ZipFile(E/('aevora-h4-'+label+'-semantic-rehashed-tampered.zip'),'x',compression=zipfile.ZIP_DEFLATED) as bad:
        for name,data in files.items():bad.writestr(name,data)
    assert record(E,'h4-independent-'+label+'-semantic-reject',['python3','-I',str(verifier),'verify',str(E/('aevora-h4-'+label+'-semantic-rehashed-tampered.zip')),'--json'])==2
    needles,classes=patterns(A);hits=[];badpaths=[];expanded=0
    with zipfile.ZipFile(bundle) as z:
        manifest=json.loads(z.read('MANIFEST.json'));paths=[v['source_path'] for v in manifest['entries']]
        forbidden={'hidden_tests','reference_patches','private_manifests','private_labels','participant','workspace','candidate','codex-state','.git'}
        badpaths=[p for p in paths if set(p.split('/'))&forbidden];assert not badpaths
        for info in z.infolist():
            data=z.read(info.filename);expanded+=len(data)
            if any(n in data for n in needles):hits.append(info.filename)
    assert not hits
    required=['g5/FRESH_NATIVE_FACT_CHECK.json','g5/public-safety-final/RESULT.json','g5/EMPTY_BRIDGE_FINAL_JUNIT_CHECK.json','g5/history-preservation-02/RESULT.json','reports/AEVORA_H4_VALIDATION_REPORT.md','reports/AEVORA_H4_TRACEABILITY_MATRIX.csv']
    assert all(p in paths for p in required)
    for rid in ['231d9138-0717-45af-a80e-a45c3bf67f68','238caf3b-957f-4ae2-bb4a-8fc21a3c4c7f','3c307462-1941-4da3-93ad-5f10f7b09ddd']:
        assert any('/runs/'+rid+'/codex_events.jsonl' in p for p in paths) and any('/runs/'+rid+'/aevora_mcp_events.jsonl' in p for p in paths)
        assert not any('/runs/'+rid+'/evaluation_report.json' in p for p in paths)
    assert any('/runs/bc47e91e-ce45-4641-8068-94d06deb5f3f/external_report.json' in p for p in paths)
    assert any('/runs/81d8c54f-43c1-4cd8-8963-ce7f23534080/' in p and '/native_rollouts/' in p for p in paths)
    frozen=json.loads((A/'EVIDENCE_MANIFEST.json').read_text());mismatch=[]
    for rel,h in frozen['ordinary_files_sha256'].items():
        p=A/rel
        if not p.is_file() or p.is_symlink() or digest(p)!=h:mismatch.append(rel)
    assert not mismatch and digest(bundle)==expected
    result={'status':'PASS','bundle_sha256':expected,'bundle_bytes':bundle.stat().st_size,'deterministic_repeat_equal':True,'actual_verifier_exit':0,'actual_byte_negative_exit':2,'actual_rehashed_semantic_negative_exit':2,'verifier_source_sha256':digest(verifier),'included_source_files':len(paths),'expanded_zip_bytes_scanned':expanded,'actual_secret_classes':classes,'secret_or_individual_hash_matches':hits,'private_source_paths':badpaths,'full_files_rehashed':len(frozen['ordinary_files_sha256']),'full_mismatches':mismatch,'full_manifest_sha256':digest(A/'EVIDENCE_MANIFEST.json'),'full_checksums_sha256':digest(A/'SHA256SUMS'),'all_five_runtime_attempts_accounted':True,'all_completed_native_streams_included':True,'four_actual_public_patch_negative_runs_verified':'FAIL with complete suite; not task success','private_reference_patches':'NOT_INCLUDED','qualification':'MAINTAINER_AUDIT. Local consistency, no origin attestation; unavailable original bytes remain UNVERIFIED. No Full writes.','at':now()}
    write(E/'DELIVERY_CHECKS.json',result);print(json.dumps(result));return 0

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='v3');a=p.parse_args()
    if not a.label.replace('-','').isalnum():raise ValueError('Simple evidence version required')
    raise SystemExit(main(a.label))
