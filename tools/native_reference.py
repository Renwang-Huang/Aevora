"""Generate public native compatibility vectors from the current Python Core.

No database, model, private evaluator, or historical archive is loaded. Expected
bytes are produced by Core; native tests must not generate their own oracle.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import runpy
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'aevora_core/src'))
from aevora.models import canonical_json, schema_catalog, _PUBLIC_FIELDS
from aevora.governance import project
from aevora.candidate import lifecycle_next_steps, candidate_checklist


def reference():
    inputs = ['null', 'true', 'false', '0', '-0', '1', '1.0', '1e0', '-0.0',
        '-0e2', '1e-999', '-1e-999', '1e-4', '1e-5', '1e15', '1e16', '1.2345678901234567e20',
        str(2**128), str(-(2**128)), '[]', '{}',
        '{"z":1.0,"a":1,"unknown":null,"known":false}',
        json.dumps({'unicode': '中文\u2028\u2029😀<&>/', '\x00': '\b\f\n\r\t\x1f'}),
        '[1,1.0,true,null,"UNKNOWN",{"state":"NOT_OBSERVED"}]']
    randomizer = random.Random(160648)
    for _ in range(256):
        number = struct.unpack('>d', randomizer.getrandbits(64).to_bytes(8, 'big'))[0]
        if math.isfinite(number):
            inputs.append(json.dumps({'value': number}))
    cases = []
    for raw in inputs:
        encoded = canonical_json(json.loads(raw))
        cases.append({'input': raw, 'canonical': encoded,
            'sha256': hashlib.sha256(encoded.encode('utf-8')).hexdigest()})
    schemas = {}
    for version in ['aevora.graph/1.0', 'aevora.graph/1.1', 'aevora.graph/1.2']:
        row = schema_catalog(version)
        schemas[version] = {k: sorted(v) if isinstance(v, (set, frozenset)) else v for k,v in row.items()}
    as_of = '2026-10-24T00:00:00+00:00'
    legacy = {'revisions':[{'record':{'id':'revision:legacy','revision_reason':'initial_verified_history_import'},
        'rule_ids':['rule:legacy'],'complete':True}], 'events':[], 'supersedes':[]}
    views = [{'revisions':[], 'events':[], 'supersedes':[]}, legacy]
    for event_type in ['withdraw', 'expire', 'restrict_scope']:
        for scope in [{}, {'operation_semantics':['conditional_write']}]:
            changed = json.loads(json.dumps(legacy))
            changed['events'] = [{'record':{'id':'governance:one','target_label':'ExperienceRevision',
                'target_id':'revision:legacy','event_type':event_type,'effective_at':'2026-10-20T00:00:00+00:00',
                'scope':scope,'material_fact_keys':list(scope)}, 'complete':True,'edge_present':True}]
            views.append(changed)
    governance = []
    for view in views:
        for context in [{}, {'operation_semantics':'conditional_write'}, {'operation_semantics':None}]:
            governance.append({'view':view,'context':context,'as_of':as_of,'expected':project(view,context,as_of)})
    console = runpy.run_path(str(ROOT / 'tools/public_evidence/projection.py'))
    sys.path.insert(0, str(ROOT / 'console/src'))
    from aevora_observatory.projection import ReplayReader
    replay = ReplayReader(ROOT / 'demo', 'c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776')
    replay_cases = []
    for case,stage in [('case-a','before'),('case-b','before'),('case-c','before'),('case-c','after'),('case-c','restored')]:
        value = replay.overview(case, stage=stage)
        replay_cases.append({'case':case, 'stage':stage, 'sha256':hashlib.sha256(canonical_json(value).encode()).hexdigest()})
    return {'schema_version': 'aevora.native-reference/1', 'canonical_cases': cases, 'governance_cases':governance,
        'candidate_checklists': [{'body':body,'state':state,'expected':candidate_checklist(body,state)}
            for body in [{}, {'necessary_conditions':{'runtime_engine':['go_native']},'scope':{'storage_backend':['sqlite']}},
                         {'necessary_conditions':{'runtime_os':['linux']},'scope':{'runtime_os':['linux']},'unknown_fields':['runtime_os']}]
            for state in ['PROPOSED','EVIDENCE_PENDING','ADMITTED_BOUNDED','PUBLISHED','WITHDRAWN']],
        'console_fields': {k:v.split() for k,v in sorted(console['FIELDS'].items())},
        'console_facts': sorted(console['FACTS']),
        'replay_cases': replay_cases,
        'lifecycle_guidance': {s:lifecycle_next_steps(s) for s in ['PROPOSED','EVIDENCE_PENDING','ADMITTED_BOUNDED','PUBLISHING','PUBLISHED','REJECTED','WITHDRAWN','SUPERSEDED']},
        'schemas': schemas, 'public_fields': {k:list(v) for k,v in sorted(_PUBLIC_FIELDS.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'go-runtime/contracts/reference.json'
    raw = (json.dumps(reference(), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    if args.check:
        if not target.is_file() or target.read_bytes() != raw:
            raise SystemExit('Native reference fixtures differ from current Python Core')
    else:
        target.write_bytes(raw)
    print(json.dumps({'status':'PASS', 'cases':len(reference()['canonical_cases']), 'database':'NOT_USED'}))


if __name__ == '__main__':
    main()
