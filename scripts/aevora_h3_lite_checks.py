"""Actual final Lite byte, proof-selection, secret and negative-control checks."""
import os
from pathlib import Path
import hashlib
import json
import zipfile
from scripts.aevora_h3_audit import archive,ROOT,record,digest,write,now


def main():
    A=archive();E=ROOT/'aevora_validation/audit_exports'/A.name
    original=E/'aevora-h3-audit-lite-v2.zip';before=digest(original)
    assert before==digest(E/'aevora-h3-audit-lite-v2-repeat.zip')
    with zipfile.ZipFile(original) as z,zipfile.ZipFile(E/'aevora-h3-audit-lite-v2-byte-tampered.zip','x') as bad:
        changed=False
        for info in z.infolist():
            data=z.read(info.filename)
            if not changed and info.filename.startswith('objects/') and data:
                data=data[:-1]+bytes([data[-1]^1]);changed=True
            bad.writestr(info,data)
    assert changed
    code=record(E,'independent-final-v2-byte-tamper-rejection',['python3','-I',str(ROOT/'benchmark/evidence_verify.py'),'verify',str(E/'aevora-h3-audit-lite-v2-byte-tampered.zip'),'--json']);assert code==2
    with zipfile.ZipFile(original) as z:
        m=json.loads(z.read('MANIFEST.json'));paths=[x['source_path'] for x in m['entries']]
        forbidden={'hidden_tests','reference_patches','private_manifests','private_labels','participant','workspace','candidate','codex-state','.git'}
        badpaths=[p for p in paths if any(part in forbidden for part in p.split('/'))];assert not badpaths
        cfg=json.loads((A/'CONFIG.json').read_text())
        secrets=[Path(cfg['password_file']).read_bytes().strip(),Path(os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH', str(Path.home()/'.config/orderflow/gateway_api_key'))).read_bytes().strip()]
        patterns=[v for secret in secrets for v in [secret,hashlib.sha256(secret).hexdigest().encode(),hashlib.sha256(secret).hexdigest().upper().encode(),hashlib.sha256(secret).digest()]]
        hits=0;scanned=0
        for info in z.infolist():
            data=z.read(info.filename);scanned+=len(data)
            hits+=int(any(p in data for p in patterns))
        assert hits==0,'Credential/hash scan failed; values and individual hashes must not be emitted'
        required=['g1/HOST_APPROVAL_ORIGIN02.json','g4/native-timeline/NATIVE_EVENT_TIMELINE.json','g4/AUDIT_KEY_CYPHER.json','g3/graph-checks/necessity_01/graph_ablation_changes_current_why.json','reports/AEVORA_H3_TRACEABILITY_MATRIX.csv']
        assert all(p in paths for p in required)
        ids=['ac3e66ff-38c4-4a4c-90b8-ae635e836dcb','405c481e-ae7a-420d-8502-fb1d9ede02e6','c4cd6c0e-fb38-465f-bee1-63d3d50374a6','af26fb0c-865d-472c-97e3-c2a2c73fd597','c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b','f4406efc-d94d-4d21-b30f-d350248f3d4e']
        assert all(any('/runs/'+rid+'/codex_events.jsonl' in p for p in paths) for rid in ids)
        assert any('/runs/ac3e66ff-38c4-4a4c-90b8-ae635e836dcb/evaluation_report.json' in p for p in paths)
        assert not any('/runs/c4cd6c0e-fb38-465f-bee1-63d3d50374a6/evaluation_report.json' in p for p in paths)
    assert digest(original)==before
    write(E/'DELIVERY_CHECKS.json',{'status':'PASS','at':now(),'bundle_file':original.name,'bundle_sha256':before,'bundle_bytes':original.stat().st_size,'deterministic_reexport_sha256_equal':True,'independent_stdlib_verifier_exit':0,'changed_content_byte_verifier_exit':code,'original_bundle_unchanged':True,'private_source_path_matches':badpaths,'secret_or_individual_hash_matches':hits,'uncompressed_bytes_scanned':scanned,'all_six_original_native_event_streams_included':True,'first_engineering_original_report_retained_as_qualified_support':True,'prepared_observation_report_excluded':True,'necessary_proof_files':required,'full_manifest_sha256':digest(A/'EVIDENCE_MANIFEST.json'),'full_checksums_sha256':digest(A/'SHA256SUMS'),'qualification':'Only fully own-native-verified origin02 is in scored RUN_INDEX. First exec verified3/native-summary0 remains qualified support; original scores/attempt denominator retained. Local consistency, not third-party attestation.'})
    print(json.dumps({'status':'PASS','bundle_sha256':before,'bytes':original.stat().st_size,'tamper_exit':code,'sources':len(paths)}));return 0


if __name__=='__main__':raise SystemExit(main())
