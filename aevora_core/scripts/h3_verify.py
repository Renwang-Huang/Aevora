"""H3-verify: bounded independent stdlib verification; never imports package code."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat


def regular_bytes(path):
    """Bounded no-follow reads, following the existing audit verifier pattern."""
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except OSError as e:raise ValueError('Unsafe member: '+path.name) from e
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>32*1024*1024:
            raise ValueError('Unsafe member: '+path.name)
        with os.fdopen(fd,'rb',closefd=False) as f:
            data=f.read(32*1024*1024+1)
        if len(data)>32*1024*1024:raise ValueError('Unsafe member: '+path.name)
        return data
    finally:os.close(fd)


def load_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def nonfinite(value):raise ValueError('Non-finite JSON number')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)


def canonical_digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def verify(root,expected_manifest_sha256=None):
    if any(q.is_symlink() for q in (root,*root.parents)) or not root.is_dir():raise ValueError('Ordinary observation directory required')
    manifest=regular_bytes(root/'MANIFEST.json');m=load_json(manifest)
    if expected_manifest_sha256 is not None and sha256(manifest).hexdigest()!=expected_manifest_sha256:
        raise ValueError('External manifest pin mismatch')
    if m.get('kind')!='AEVORA_H3_READ_ONLY_DEMO':raise ValueError('Unexpected manifest')
    if set(q.name for q in root.iterdir())!=set(m['files'])|{'MANIFEST.json'}:raise ValueError('Unexpected file set')
    members={}
    for name,h in m['files'].items():
        if '/' in name or '\\' in name or name in ('.','..'):raise ValueError('Invalid relative member')
        q=root/name
        raw=regular_bytes(q)
        if sha256(raw).hexdigest()!=h:raise ValueError('Member byte tamper: '+name)
        members[name]=raw
    life=load_json(members['CANDIDATE_LIFECYCLE.json']);events=life['events']
    if canonical_digest(life['candidate']['body'])!=life['candidate']['body_sha256'] or canonical_digest(life['head'])!=life['head_sha256']:
        raise ValueError('Candidate body/head digest mismatch')
    if life['candidate']['id']!=m['candidate_id'] or life['head']['state']!='PUBLISHED':raise ValueError('Publication lifecycle missing')
    for i,e in enumerate(events):
        if e['candidate_id']!=m['candidate_id'] or e['sequence']!=i:raise ValueError('Lifecycle identity mismatch')
        if i and (e['previous_event_id']!=events[i-1]['id'] or e['from_state']!=events[i-1]['to_state']):raise ValueError('Lifecycle chain mismatch')
    if not events or events[0]['to_state']!='PROPOSED' or events[0]['previous_event_id']:
        raise ValueError('Lifecycle genesis mismatch')
    transitions={'PROPOSED':{'EVIDENCE_PENDING','REJECTED'},'EVIDENCE_PENDING':{'ADMITTED_BOUNDED','REJECTED'},
        'ADMITTED_BOUNDED':{'PUBLISHING','WITHDRAWN'},'PUBLISHING':{'PUBLISHED','WITHDRAWN'},'PUBLISHED':{'WITHDRAWN','SUPERSEDED'}}
    if any(e['to_state'] not in transitions.get(e['from_state'],set()) for e in events[1:]):raise ValueError('Illegal lifecycle transition')
    if not any(e['to_state']=='ADMITTED_BOUNDED' for e in events) or events[-1]['to_state']!='PUBLISHED':raise ValueError('Host admission/publication absent')
    graph=load_json(members['PUBLIC_GRAPH.json']);ids={n['id'] for n in graph['nodes']}
    if len(ids)!=len(graph['nodes']):raise ValueError('Duplicate node identity')
    if any(e['source'] not in ids or e['target'] not in ids for e in graph['edges']):raise ValueError('Graph endpoint missing')
    source=[n for n in graph['nodes'] if n['label']=='SourceVerification' and n['public'].get('candidate_id')==m['candidate_id']]
    if len(source)!=1 or source[0]['public'].get('origin')!='natural_agent_run':raise ValueError('Actual natural source verification absent')
    links={(e['source'],e['relation'],e['target']) for e in graph['edges']}
    source_id=source[0]['id'];outcome_id=source[0]['public']['outcome_id']
    if (m['candidate_id'],'HAS_SOURCE_VERIFICATION',source_id) not in links:
        raise ValueError('Candidate source edge absent')
    if not any(n['id']==outcome_id and n['label']=='VerifiedOutcome' and n['public'].get('verdict')=='PASS' for n in graph['nodes']):
        raise ValueError('Source independent PASS absent')
    if not all((m['candidate_id'],'HAS_CANDIDATE_EVENT',e['id']) in links for e in events):raise ValueError('Lifecycle event edge absent')
    o=load_json(members['EXTERNAL_OBSERVATION.json'])
    if o.get('run_id')!=m['external_run_id'] or o.get('authority')!='EXTERNAL_UNVERIFIED' or o.get('trusted_outcome')!='NOT_CREATED':raise ValueError('External observation authority mismatch')
    if any(n['label']=='VerifiedOutcome' and n['public'].get('run_id')==m['external_run_id'] for n in graph['nodes']):raise ValueError('External verified outcome forbidden')
    views=load_json(members['WHEN_WHY.json'])
    positives=[c for c in views['bounded_source']['candidates'] if c['decision']=='APPLY' and c.get('principle_support_paths')]
    if not positives:raise ValueError('Bounded positive support absent')
    for c in positives:
        for path in c['principle_support_paths']:
            if len(path['path'])!=len(path['edge_types'])+1 or any((s,r,t) not in links for s,r,t in zip(path['path'],path['edge_types'],path['path'][1:])):
                raise ValueError('Displayed positive WHY path missing from actual graph')
    if not any(c['decision'] in ('VERIFY','ABSTAIN') and c.get('conflicting_premises') for c in views['independent_workers']['candidates']):raise ValueError('Negative factual condition not observed')
    return {'status':'PASS','checked_files':len(m['files']),'candidate_id':m['candidate_id'],'external_run_id':m['external_run_id'],
            'manifest_sha256':sha256(manifest).hexdigest(),'qualification':'Local bytes/relationships/authority; runtime origin, causal gain and omitted private bytes are not independently attested.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--manifest-sha256')
    a=p.parse_args()
    try:print(json.dumps(verify(a.directory,a.manifest_sha256)));raise SystemExit(0)
    except (ValueError,OSError,KeyError,TypeError) as e:print(json.dumps({'status':'FAIL','error_type':type(e).__name__,'reason':str(e)}));raise SystemExit(1)
