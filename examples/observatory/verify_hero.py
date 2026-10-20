"""Independent, bounded standard-library verifier for the PUBLIC Hero replay.

Use a trusted copy of this verifier and an externally pinned contract digest.
It checks provenance consistency, not external attestation or causal benefit.
Never imports code, connects to a database, or executes a file from the replay.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

LIMIT = 8 * 1024 * 1024
IDENTITIES = ('run_id','session_id','candidate_id','experience_id','rule_id',
              'decision_id','query_snapshot_id','outcome_id')
PUBLIC_NODE_FIELDS = {
 'Agent':'id runtime source_type', 'Task':'id public_title scenario_version', 'Context':'id facts source_type',
 'Experience':'id title public_summary strategy source_type limitations origin_run_id origin_patch_sha256 publication_candidate_id created_at',
 'ExperienceRevision':'id experience_id revision_kind revision_reason base_revision_ids created_at declared_rule_id scope',
 'Rule':'id experience_id version principle strategy created_at valid_from valid_until', 'Premise':'id fact_key allowed_values required',
 'Evidence':'id source_type source_run_id public_summary attribution created_at',
 'VerifiedOutcome':'id run_id verdict test_count source_type submission_digest evaluator_fingerprint test_suite_fingerprint attribution',
 'Query':'id run_id created_at query_snapshot_ids decision_engine_version', 'QuerySnapshot':'id content_sha256 created_at',
 'Decision':'id run_id query_id experience_id decision reason verification_steps authority adoption attribution created_at query_snapshot_id',
 'ObservedAction':'id run_id submission_digest patch_sha256 source_type authority attribution mental_influence strategy_association created_at',
 'Feedback':'id experience_id outcome_id attribution feedback_status source_type',
 'GovernanceEvent':'id target_id target_label event_type authority source_type public_reason scope effective_at created_at',
 'AuditEvent':'id event_type candidate_id record_id authority public_reason created_at','Schema':'id version',
 'Candidate':'id run_id body_sha256 authority provenance created_at schema_version',
 'LifecycleHead':'id candidate_id state sequence event_id',
 'CandidateEvent':'id candidate_id from_state to_state sequence previous_event_id event_key authority principal reason created_at',
 'SourceVerification':'id candidate_id run_id origin authority source_sha256 submission_sha256 outcome_id facts native_thread_id source_epoch causal_benefit',
 'ExternalObservation':'id run_id status authority source_sha256 public_summary created_at trusted_outcome attribution',
}


def strict_json(data):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    def finite(v):raise ValueError('Nonfinite JSON value')
    return json.loads(data,object_pairs_hook=pairs,parse_constant=finite)


def read(root,relative):
    p=PurePosixPath(relative)
    if p.is_absolute() or not p.parts or '..' in p.parts or str(p)!=relative:
        raise ValueError('Noncanonical artifact path')
    target=root.joinpath(*p.parts)
    if any(x.is_symlink() for x in (target,*target.parents)):
        raise ValueError('Linked artifact path')
    fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>LIMIT:
            raise ValueError('Bounded ordinary single-link file required')
        with os.fdopen(fd,'rb',closefd=False) as f:data=f.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError('Artifact too large')
        return data
    finally:os.close(fd)


def check(ok,message):
    if not ok:raise ValueError(message)


def clock(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    check(d.utcoffset() is not None,'Timestamp requires timezone')
    return d


def graph_check(graph):
    nodes={n['id']:n for n in graph['nodes']}
    edges={e['id']:e for e in graph['edges']}
    check(len(nodes)==len(graph['nodes']) and len(edges)==len(graph['edges']),'Duplicate graph identity')
    for e in edges.values():
        check(e['source'] in nodes and e['target'] in nodes,'Dangling actual graph endpoint')
        check(re.fullmatch('[A-Z_]+',e['relation']) is not None,'Invalid relation type')
    for n in nodes.values():
        if 'public' in n:
            check(not set(n['public'])-set(PUBLIC_NODE_FIELDS.get(n['label'],'id').split()),'Non-public graph properties disclosed')
            check(n['public'].get('id')==n['id'],'Projected node identity differs from graph')
    return nodes,edges


def path_check(row,edges):
    for path in row['support_paths']+row['counterexample_paths']:
        check(len(path['path'])==len(path['edge_types'])+1,'Invalid path length')
        for s,r,t in zip(path['path'],path['edge_types'],path['path'][1:]):
            check(any((e['source'],e['relation'],e['target'])==(s,r,t) for e in edges.values()),'Displayed path absent from actual graph')


def verify(root,expected_sha256):
    root=Path(root).absolute()
    check(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)),'Ordinary root required')
    raw=read(root,'hero_scenario_contract.json')
    check(re.fullmatch('[0-9a-f]{64}',expected_sha256 or '') is not None,'External contract SHA256 pin required')
    check(sha256(raw).hexdigest()==expected_sha256,'Contract SHA256 differs from external pin')
    c=strict_json(raw)
    check(c['schema_version']=='aevora.hero/1.0' and c['visibility']=='PUBLIC' and c['mode']=='REPLAY','Unexpected contract authority/mode')
    check(c['causal_benefit']=='UNKNOWN' and c['agent_adoption']=='UNKNOWN','Unsupported causal/adoption assertion')
    artifacts={}
    check(len(c['artifacts'])<=32,'Too many artifacts')
    for name,ref in c['artifacts'].items():
        check(ref['visibility']=='PUBLIC','Private artifact cannot enter public replay')
        data=read(root,ref['artifact_path'])
        check(sha256(data).hexdigest()==ref['sha256'],'Artifact hash mismatch: '+name)
        check(re.fullmatch('[0-9a-f]{64}',ref['source_sha256']) is not None,'Source fingerprint missing')
        artifacts[name]=strict_json(data)
    g=artifacts['graph'];nodes,edges=graph_check(g)
    life=artifacts['lifecycle']; origin=artifacts['origin']; readback=artifacts['readback']
    candidate=life['candidate']; events=life['events'];head=life['head']
    check(candidate['run_id']==origin['run_id'],'Candidate/source Run mismatch')
    check(candidate['body_sha256']==origin['candidate_body_sha256'],'Proposal body/source mismatch')
    check(events and head['state']=='PUBLISHED','Lifecycle is not a published history')
    previous=None;state=None;previous_time=None
    transitions={None:{'PROPOSED'},'PROPOSED':{'EVIDENCE_PENDING'},'EVIDENCE_PENDING':{'ADMITTED_BOUNDED'},'ADMITTED_BOUNDED':{'PUBLISHING'},'PUBLISHING':{'PUBLISHED'}}
    for i,e in enumerate(events):
        check(e['candidate_id']==candidate['id'] and e['sequence']==i and e['from_state']==state and e['previous_event_id']==previous,'Broken lifecycle event chain')
        check(e['to_state'] in transitions.get(state,set()),'Invalid lifecycle transition')
        at=clock(e['created_at']);check(previous_time is None or at>=previous_time,'Lifecycle time reversal')
        check(e['authority']==('UNTRUSTED_PROPOSAL' if i==0 else 'TRUSTED_HOST_REVIEW'),'Untrusted actor promoted to Host')
        previous,state,previous_time=e['id'],e['to_state'],at
    check((head['event_id'],head['sequence'],head['candidate_id'])==(previous,len(events)-1,candidate['id']),'Lifecycle head mismatch')
    source=nodes[origin['source_verification_id']]['public']; outcome=nodes[origin['outcome_id']]['public']
    check(source['run_id']==origin['run_id'] and source['candidate_id']==candidate['id'] and source['outcome_id']==origin['outcome_id'],'Source verification identity mismatch')
    check(source['submission_sha256']==origin['patch_sha256'],'Host source patch mismatch')
    check(source['authority']=='TRUSTED_HOST_SOURCE_VERIFIER' and source['causal_benefit']=='UNKNOWN','Host source authority changed')
    for s,r,t in [(candidate['id'],'HAS_SOURCE_VERIFICATION',source['id']),
                  (life['experience_id'],'PUBLISHED_FROM',candidate['id']),
                  (candidate['id'],'HAS_LIFECYCLE',head['id']),
                  *[(candidate['id'],'HAS_CANDIDATE_EVENT',e['id']) for e in events]]:
        check(any((e['source'],e['relation'],e['target'])==(s,r,t) for e in edges.values()),'Lifecycle/source relationship absent')
    check(outcome['run_id']==origin['run_id'] and outcome['verdict']=='PASS' and outcome['test_count']==origin['test_counts']['passed'],'Independent outcome mismatch')
    tc=origin['test_counts'];check(tc['collected']==tc['passed'] and tc['failed']==tc['errors']==tc['skipped']==0 and origin['pytest_exit_code']==0,'Source evaluation incomplete')
    check(clock(origin['started_at'])<clock(origin['ended_at']),'Invalid source runtime interval')
    children=origin['children'];check(len(children)>=2 and len({x['agent_id'] for x in children})==len(children),'Distinct native children required')
    for child in children:
        check(child['parent_thread_id']==origin['session_id'] and child['verified'] and child['completed'],'Native child evidence incomplete')
        for key in ('spawn','completion','parent_receipt'):
            ref=child[key];check(ref['line']>0 and re.fullmatch('[0-9a-f]{64}',ref['sha256']) is not None,'Native raw reference absent')
        check(clock(child['spawn']['timestamp'])<=clock(child['completion']['timestamp']),'Native completion before spawn')
    check(readback['run_id']!=origin['run_id'] and readback['thread_id']!=origin['session_id'],'Readback must use a different Session')
    check(readback['target_experience_id']==life['experience_id'] and readback['native_turn_complete'] and readback['evaluation']=='NOT_EXECUTED' and readback['failure_kind']=='NO_PATCH','Readback incorrectly promoted to engineering success')
    views=artifacts['views']
    for rows in views.values():
        for row in rows:path_check(row,edges)
    evolve=artifacts['evolution'];bn,be=graph_check(evolve['before_graph']);an,ae=graph_check(evolve['after_graph'])
    check(bn==an,'Ablation also changed nodes')
    removed=set(be)-set(ae)
    check(removed=={evolve['selected_edge']['id']} and not set(ae)-set(be),'Expected exactly one actual removed edge')
    edge=evolve['selected_edge'];check(be[edge['id']]==edge and edge['relation']=='VERIFIES','Ablation relationship/endpoint mismatch')
    before,after,restored=evolve['before'],evolve['after'],evolve['restored']
    check(before['experience_id']==after['experience_id']==restored['experience_id'],'Cross-rule evolution fabricated')
    check(before['decision']=='APPLY' and after['decision']=='VERIFY' and restored['decision']=='APPLY','Evolution decisions do not match recorded control')
    path_check(before,be);path_check(after,ae)
    check(before['support_paths'] and not after['support_paths'] and restored['support_paths']==before['support_paths'],'Support paths do not explain evidence evolution')
    check(before['retrieval_snapshot_sha256']==evolve['historical_replay']['retrieval_snapshot_sha256']==restored['retrieval_snapshot_sha256'],'Historical retrieval was rewritten')
    check(after['retrieval_snapshot_sha256']!=before['retrieval_snapshot_sha256'],'No actual retrieval difference')
    check(evolve['classification']=='MAINTAINER_CONTROLLED_ABLATION' and evolve['agent_outcome_id'] is None,'Controlled intervention cannot become Agent Outcome')
    query_ids={q['id'] for q in artifacts['queries']['queries']}
    check(evolve['delete_query_id'] in query_ids and evolve['restore_query_id'] in query_ids,'Actual mutation queries missing')
    delete=next(q for q in artifacts['queries']['queries'] if q['id']==evolve['delete_query_id'])
    check('DELETE r' in delete['cypher'] and edge['id'] in delete['cypher'] and delete['status']=='RETURNED','Delete statement/actual edge mismatch')
    cases=c['acts'];check([x['case_id'] for x in cases]==['case-a','case-b','case-c'],'Explicit three-case narrative required')
    for case in cases:
        check(case['mode']=='REPLAY' and case['visibility']=='PUBLIC','Case mode/visibility mismatch')
        check(all(k in case for k in IDENTITIES),'Missing explicit unavailable identity')
        check(case['causal_benefit']=='UNKNOWN' and case['agent_adoption']=='UNKNOWN','Case claims unverified benefit')
    case_a,case_b,case_c=cases
    check((case_a['run_id'],case_a['session_id'],case_a['candidate_id'],case_a['experience_id'],case_a['outcome_id'])==(origin['run_id'],origin['session_id'],candidate['id'],life['experience_id'],origin['outcome_id']),'Act I bound identity mismatch')
    check(case_a['source_commit']==origin['source_commit'] and case_a['source_tree']==origin['source_tree'],'Source epoch falsely attributed')
    b=next(x for x in views['independent_workers'] if x['experience_id']==case_b['experience_id'])
    check(case_b['rule_id'] in b['rule_ids'] and b['decision']=='ABSTAIN' and bool(b['conflicting_premises']),'Act II rule/conflict absent')
    check(case_b['decision_id'] is None and case_b['query_snapshot_id'] is None,'Read-only H3 view has no persisted Decision/Snapshot ID')
    check(case_c['experience_id']==before['experience_id'] and case_c['query_snapshot_id']==before['query_snapshot_id'] and case_c['outcome_id'] is None and case_c['candidate_id'] is None,'Act III fabricated cross-case inheritance')
    check(c['same_experience_across_acts'] is False,'Separate examples must not imply a unified lineage')
    pilot=artifacts['pilot'];check(pilot['governance']['passed']==pilot['raw_memory']['passed']==7 and pilot['verified_outcomes']==0,'Raw/Governance result misrepresented')
    check(pilot['authority']=='EXTERNAL_UNVERIFIED' and pilot['causal_benefit']=='UNKNOWN','External self-test promoted to trusted/causal')
    for side in ['governance','raw_memory']:
        result=pilot[side]
        check(result['exit_code']==0 and result['verified_outcome_count']==0 and result['passed']==len(result['public_test_identities']) and len(set(result['public_test_identities']))==result['passed'],'Ordinary result/identity mismatch')
    check(pilot['governance']['baseline_tree_sha256']==pilot['raw_memory']['baseline_tree_sha256'] and set(pilot['governance']['public_test_identities'])==set(pilot['raw_memory']['public_test_identities']),'Pilot conditions are not the same baseline/tests')
    claims={x['id']:x for x in c['claims']}
    check(set(claims)=={'birth','challenge','evolution','external-comparison'},'Unexpected unsupported narrative claim')
    check(all(x['causal_benefit']=='UNKNOWN' and x['agent_adoption']=='UNKNOWN' and x['artifact'] in artifacts for x in claims.values()),'Unsupported claim authority')
    return {'status':'PASS','mode':'REPLAY','visibility':'PUBLIC','acts':3,'native_children':len(children),
            'artifacts':len(artifacts),'contract_sha256':expected_sha256,'causal_benefit':'UNKNOWN',
            'assurance':'Externally pinned local evidence consistency; not independent historical attestation.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--sha256',required=True);a=p.parse_args()
    try:print(json.dumps(verify(a.root,a.sha256),sort_keys=True));return 0
    except (ValueError,KeyError,TypeError,OSError,IndexError) as e:
        print(json.dumps({'status':'FAIL','error':str(e)}));return 1


if __name__=='__main__':raise SystemExit(main())
