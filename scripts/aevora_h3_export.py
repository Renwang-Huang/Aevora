"""Aevora H3 selection over the unchanged Full/CAS/redaction/stdlb verifier.

Engineering Runs remain scored. Read-only and external Sessions are only
supporting native evidence; external public tests never become Oracle outcomes.
Run in a disposable host interpreter after all writers and Full sealing stop.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path,PurePosixPath
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import aevora_h2_export as old
from benchmark import evidence_export as legacy,evidence_verify

VERSION='aevora.h3-audit-lite/1.0'


def supporting_sessions(root,indexed,ids,engineering_ids=()):
    result={}
    for rid in ids:
        matches=[str(PurePosixPath(p).parent) for p in indexed if p.endswith(('/observation_report.json','/external_report.json')) and PurePosixPath(p).parent.name==rid]
        if len(matches)!=1:raise ValueError('Supporting native Session absent or ambiguous')
        prefix=matches[0];seal=json.loads(legacy._read_regular(root,prefix+'/run_evidence_manifest.json'))
        if seal.get('run_id')!=rid or not all(indexed.get(prefix+'/'+p)==h for p,h in seal['files'].items()):raise ValueError('Supporting Session seal changed')
        runtime=json.loads(legacy._read_regular(root,prefix+'/runtime_metadata.json'))
        if runtime.get('run_id')!=rid or runtime.get('fresh_session') is not True or (root/prefix/'codex-state').exists():raise ValueError('Supporting Session not fresh/stopped')
        if prefix+'/external_report.json' in indexed:
            report=json.loads(legacy._read_regular(root,prefix+'/external_report.json'))
            if report.get('trusted_outcome')!='NOT_CREATED' or report.get('verified_outcome_count')!=0 or prefix+'/evaluation_report.json' in indexed:raise ValueError('External Session authority mismatch')
        else:
            report=json.loads(legacy._read_regular(root,prefix+'/observation_report.json'))
            if report.get('evaluation')!='NOT_EXECUTED' or report.get('source_unchanged') is not True or report.get('native_turn_complete') is not True:raise ValueError('Read-only evidence incomplete')
            prepared=json.loads(legacy._read_regular(root,prefix+'/evaluation_report.json'))
            if prepared.get('overall_status')!='PREPARED' or prepared.get('test_results') is not None:raise ValueError('Observation acquired a task grade')
        result[rid]=prefix
    for rid in engineering_ids:
        if rid in result:raise ValueError('Supporting classifications must be disjoint')
        prefix=legacy._run_roots(indexed,[rid])[rid]
        seal=json.loads(legacy._read_regular(root,prefix+'/run_evidence_manifest.json'))
        if seal.get('run_id')!=rid or not all(indexed.get(prefix+'/'+p)==h for p,h in seal['files'].items()):raise ValueError('Engineering attempt seal changed')
        runtime=json.loads(legacy._read_regular(root,prefix+'/runtime_metadata.json'))
        summary=json.loads(legacy._read_regular(root,prefix+'/native_rollout_summary.json'))
        if runtime.get('fresh_session') is not True or (root/prefix/'codex-state').exists():raise ValueError('Supporting engineering Session active or not fresh')
        # Preserve the original exec-based Runtime and evaluation scores, but
        # do not weaken the unchanged Lite verifier's stronger own-rollout
        # identity requirements or manufacture a replacement summary.
        if summary.get('run_id')!=rid or summary.get('subagents',{}).get('availability')!='UNAVAILABLE':raise ValueError('Explicit unavailable-native-summary qualification required')
        report=json.loads(legacy._read_regular(root,prefix+'/evaluation_report.json'))
        if report.get('run_id')!=rid:raise ValueError('Supporting original report identity differs')
        result[rid]=prefix
    return result


def public_extra(path):
    parts=PurePosixPath(path).parts
    if 'aevora_core' in parts:
        local=parts[parts.index('aevora_core')+1:]
        return bool(local and ((local[0]=='scripts' and path.endswith('.py')) or local[0]=='examples'
                              or local in [('pyproject.toml',),('MANIFEST.in',)]))
    return (bool(parts[-1].startswith('aevora_h3_') and path.endswith('.py'))
            or parts[-2:]==('integrations','aevora.py')
            or parts[-2:]==('scripts','aevora_build_backend.py')
            or old._inside_snapshot(path) and parts[-1] in {'pyproject.toml','MANIFEST.in'})


def worker(root,output,runs,supports,stamp,engineering_supports=()):
    indexed,provenance=legacy._source_index(root)
    if provenance['index_type']!='FULL_ARCHIVE_MANIFEST':raise ValueError('Final Full seal required')
    if set(runs)&(set(supports)|set(engineering_supports)):raise ValueError('Scored and supporting identities overlap')
    observations=supporting_sessions(root,indexed,supports,engineering_supports)
    original=legacy._selection
    def select(actual_root,actual_index,roots):
        if actual_root!=root or actual_index!=indexed:raise ValueError('Full admission changed')
        selected=old.h2_selection(root,indexed,roots,observations,())
        for source in indexed:
            if not old._allowed(source):continue
            parts=PurePosixPath(source).parts;name=parts[-1]
            if public_extra(source) and old._support_size(root,source)<=old.MAX_SUPPORT_BYTES:selected.add(source)
            if '/g4/demo/' in '/'+source or source.startswith('g4/demo/'):
                if name.endswith('.json') and old._support_size(root,source)<=8*1024*1024:selected.add(source)
            if source.endswith('/PUBLIC_GRAPH.json') and old._support_size(root,source)<=8*1024*1024:selected.add(source)
            # Explicit bounded lifecycle/control receipts are not recognized
            # by the legacy filename-token selector. Never include raw private
            # graph dumps or secret paths through this extension.
            proof=(source in {'g1/HOST_APPROVAL_ORIGIN02.json','g3/PILOT_PUBLIC_CORPUS.json',
                             'g4/native-timeline/NATIVE_EVENT_TIMELINE.json','g4/AUDIT_KEY_CYPHER.json'}
                   or source.startswith('reports/') and name.endswith(('.md','.csv'))
                   or source.startswith('g1/review/origin02/') and name.endswith('.json')
                   or source.startswith('g1/graph-checks/') and name.endswith('.json') and name not in {'BEFORE.json','AFTER.json'}
                   or source.startswith('g3/graph-checks/necessity_01/') and name.endswith('.json') and name not in {'BEFORE.json','AFTER.json'})
            if proof and old._support_size(root,source)<=8*1024*1024:selected.add(source)
            if any(source.startswith(p+'/') for p in observations.values()):
                local=next(source[len(p)+1:] for p in observations.values() if source.startswith(p+'/'))
                if local in {'external_report.json','observation_report.json','EXTERNAL_OBSERVATION.json','submission_integrity.json','PROJECT_GIT.json'} or local in {'public-tests/command.json','public-tests/stdout.log','public-tests/stderr.log'}:selected.add(source)
        selected.difference_update(p+'/evaluation_report.json' for rid,p in observations.items() if rid not in engineering_supports)
        # The reused H2 selector drops all observation report filenames early.
        # Explicitly restore this sealed *executed* original as qualified
        # supporting evidence; never restore a read-only PREPARED report.
        selected.update(observations[rid]+'/evaluation_report.json' for rid in engineering_supports)
        return selected
    try:
        legacy._selection=select
        result=legacy.export_archive(root,output,run_ids=runs,created_at=stamp)
    finally:legacy._selection=original
    independent=evidence_verify.verify_bundle(output)
    if result['bundle_sha256']!=independent['bundle_sha256']:raise ValueError('Independent verification mismatch')
    result.update(adapter_version=VERSION,supporting_session_ids=supports,independent_verification=independent,
       supporting_engineering_attempt_ids=list(engineering_supports),
       supporting_engineering_qualification='Original report/runtime/raw events included unchanged except existing redaction; unavailable own-native summary is not promoted into fully verified scored Run index; attempt denominator retained in H3 comparison/reports',
       external_authority='EXTERNAL_UNVERIFIED; NOT_SCORED_RUN_INDEX',native_event_projection='Complete files with original/export line SHA and existing redaction',
       compatibility='Existing ORDERFLOW_AUDIT_LITE envelope; Aevora H3 selection; Benchmark retains independent identity',adapter_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--run-id',action='append',required=True);p.add_argument('--supporting-session',action='append',default=[]);p.add_argument('--created-at',required=True)
    p.add_argument('--supporting-engineering-attempt',action='append',default=[])
    a=p.parse_args()
    try:print(json.dumps(worker(a.archive.absolute(),a.output.absolute(),a.run_id,a.supporting_session,a.created_at,a.supporting_engineering_attempt),sort_keys=True));raise SystemExit(0)
    except (ValueError,OSError,KeyError,TypeError) as e:print(json.dumps({'status':'ERROR','adapter_version':VERSION,'error_type':type(e).__name__,'reason':str(e)}));raise SystemExit(2)
