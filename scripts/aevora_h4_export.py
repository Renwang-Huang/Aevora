"""H4 bounded reviewer selection over existing CAS/redaction/stdlib verifier.

Only public benign-comment manual negative Runs are in RUN_INDEX: private reference repair
bytes remain Full pointers. Positive reports/JUnit/Oracle are qualified support.
Ordinary native observations never become independently scored outcomes.
"""
import argparse,json
from hashlib import sha256
from pathlib import Path,PurePosixPath
from benchmark import evidence_export as legacy,evidence_verify
from scripts.aevora_h2_export import h2_selection,_allowed,_support_size,_run_assets,MAX_SUPPORT_BYTES
from scripts.aevora_h3_export import supporting_sessions

def worker(root,output,runs,supports,stamp):
    indexed,provenance=legacy._source_index(root)
    if provenance['index_type']!='FULL_ARCHIVE_MANIFEST':raise ValueError('Final Full seal required')
    observations=supporting_sessions(root,indexed,supports)
    failed_prefix='g1/native/fresh_empty_readonly_01/runs/bc47e91e-ce45-4641-8068-94d06deb5f3f'
    failed=json.loads(legacy._read_regular(root,failed_prefix+'/external_report.json'))
    if failed.get('failure_kind')!='AEVORA_STARTUP_FAILED' or failed.get('native_exit_code') is not None or failed.get('session_id')!='UNAVAILABLE':raise ValueError('Original failed startup classification changed')
    original=legacy._selection
    def select(actual_root,actual_index,roots):
        if actual_root!=root or actual_index!=indexed:raise ValueError('Full admission changed')
        selected=h2_selection(root,indexed,roots,observations,())
        selected.update(_run_assets(indexed,failed_prefix))
        selected.update(failed_prefix+'/'+p for p in ['external_report.json','EXTERNAL_OBSERVATION.json'])
        selected.update(['g5/FRESH_NATIVE_FACT_CHECK.json','g5/EMPTY_BRIDGE_FINAL_JUNIT_CHECK.json','g5/INSTALLED_SOURCE_BYTE_CHECK.json','g5/G4_PROPOSAL_FAILURE_RAW_REVIEW.json'])
        for source in indexed:
            if not _allowed(source):continue
            parts=PurePosixPath(source).parts;name=parts[-1]
            # Actual diagrams/projections, UI screenshots, command/HTTP receipts
            # and source needed to audit the thin public reader. No raw DB dump.
            proof=(source.startswith('reports/') and name.endswith(('.md','.csv'))
                or source.startswith(('g3/browser-validation-07/','g5/public-image-browser-01/','g5/public-image-browser-final/')) and name.endswith('.json')
                or source.startswith('g4/live-observation-03/') and name.endswith('.json')
                or source.startswith(('g5/fresh-product-protocol-02/','g5/provider-auth-denial/')) and name.endswith(('.json','.jsonl'))
                or source.startswith('g4/actual-necessity-02/') and name.endswith('.json') and name not in {'BEFORE.json','AFTER.json'}
                or '/artifacts/oracle-' in source and name.endswith('.json')
                or source.endswith('/evaluation_report.json') and not source.startswith(tuple(p+'/' for p in observations.values()))
                or source in {'g4/INCOMPLETE_ATTEMPT_01.json','g4/STOPPED_ATTEMPT_01_NATIVE_RECOVERY.json'})
            if proof and _support_size(root,source)<=8*1024*1024:selected.add(source)
            if source.startswith(('final/source_snapshot/','final/source_snapshot_closure/')):
                local=source.split('/',2)[2]
                if local.startswith(('h4/','console/src/','scripts/aevora_h4_')) and name.endswith(('.py','.json','.js','.css','.html','.md')) and _support_size(root,source)<=MAX_SUPPORT_BYTES:selected.add(source)
            if any(source.startswith(p+'/') for p in observations.values()):
                local=next(source[len(p)+1:] for p in observations.values() if source.startswith(p+'/'))
                if local in {'external_report.json','EXTERNAL_OBSERVATION.json','submission_integrity.json','PROJECT_GIT.json','public-tests/command.json','public-tests/stdout.log','public-tests/stderr.log'}:selected.add(source)
        # A stopped, interrupted attempt has real raw logs but no terminal grade.
        for source in indexed:
            if '/ordinary_repair_01/runs/81d8c54f-43c1-4cd8-8963-ce7f23534080/' in '/'+source and _allowed(source):
                name=PurePosixPath(source).name
                if name in {'codex_events.pending','agent_trace.pending','runtime_metadata.json','runtime_status.json','SOURCE_EPOCH.json'} or '/artifacts/native_rollouts/' in source and name.endswith('.jsonl'):selected.add(source)
        selected.difference_update(p+'/evaluation_report.json' for p in observations.values())
        # Independent verifier requires exact bytes for any indexed verified
        # patch. Therefore select only genuine no-submission negative Runs;
        # reference reports are support and private patch bytes are not exposed.
        public_patch=json.loads(legacy._read_regular(root,'g5/lite-negative-controls-02/PUBLIC_CONTROL_PATCH.json'))['sha256']
        for prefix in roots.values():
            report=json.loads(legacy._read_regular(root,prefix+'/evaluation_report.json'))
            if report.get('overall_status')!='FAIL' or (report.get('submission_integrity') or {}).get('patch_sha256')!=public_patch:raise ValueError('Only real public benign-patch negative controls may be scored')
        selected={s for s in selected if not s.endswith('/submission.diff') or any(s.startswith(p+'/') for p in [*observations.values(),*roots.values()])}
        return selected
    try:
        legacy._selection=select;result=legacy.export_archive(root,output,run_ids=runs,created_at=stamp)
    finally:legacy._selection=original
    checked=evidence_verify.verify_bundle(output)
    if result['bundle_sha256']!=checked['bundle_sha256']:raise ValueError('Independent verification mismatch')
    result.update(adapter_version='aevora.h4-audit-lite/1.0.3',adapter_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),independent_verification=checked,supporting_session_ids=supports,failed_startup='bc47e91e-ce45-4641-8068-94d06deb5f3f actual complete failure artifacts; native Session UNAVAILABLE; zero requests; not a supporting completed Session or scored Run',private_repairs='NOT_INCLUDED; private-reference PASS reports/JUnit/Oracle are supporting bytes, not independently patch-verified RUN_INDEX',ordinary_sessions='EXTERNAL_UNVERIFIED; zero VerifiedOutcome; original runtime classification preserved',incomplete_attempt='Actual stopped pending/native bytes retained; terminal exit UNAVAILABLE, no grade promotion',screenshots='Binary PNG/trace ZIP are Full pointers and separate reviewer supplement, unchanged legacy CAS accepts UTF-8 evidence only',publication='MAINTAINER_AUDIT_ONLY; never Participant/public product')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path);p.add_argument('--run-id',action='append',required=True);p.add_argument('--supporting-session',action='append',default=[]);p.add_argument('--created-at',required=True);a=p.parse_args()
    try:print(json.dumps(worker(a.archive.absolute(),a.output.absolute(),a.run_id,a.supporting_session,a.created_at),sort_keys=True));raise SystemExit(0)
    except (ValueError,OSError,KeyError,TypeError) as e:print(json.dumps({'status':'ERROR','error_type':type(e).__name__,'reason':str(e)}));raise SystemExit(2)
