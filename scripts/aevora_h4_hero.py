"""Trusted H4-G0 projection of immutable H3 evidence; no models or graph writes."""
from pathlib import Path
import argparse
import json
import re
from hashlib import sha256
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now
from examples.observatory.public_projection import project,decision_view


def build(destination=None,receipt_label='hero'):
    a=archive(); old=Path((ROOT/'aevora_validation/H3_CURRENT').read_text().strip())
    root=Path(destination or ROOT/'examples/observatory');root.mkdir(parents=True,exist_ok=True)
    out=root/'replay'; out.mkdir(mode=0o755)
    artifacts={};sources={}
    frozen=json.loads((old/'EVIDENCE_MANIFEST.json').read_text())['ordinary_files_sha256']
    def load(rel):
        p=old/rel
        if digest(p)!=frozen[rel]:raise ValueError('H3 frozen evidence changed')
        sources[rel]=digest(p);return json.loads(p.read_text())
    def emit(name,data,source):
        rel='replay/'+name+'.json';write(root/rel,data)
        artifacts[name]={'artifact_path':rel,'sha256':digest(root/rel),'source_sha256':sources[source],
                         'visibility':'PUBLIC','source_archive':old.name,'source_artifact':source,
                         'projection':'Explicit fields; omitted original bytes are NOT_INCLUDED'}
    g=load('g4/demo/PUBLIC_GRAPH.json')
    g['nodes']=[{**n,'public':project(n['label'],n['public'])} for n in g['nodes']]
    emit('graph',g,'g4/demo/PUBLIC_GRAPH.json')
    full_life=load('g4/demo/CANDIDATE_LIFECYCLE.json');candidate=full_life['candidate']
    events=[]
    for e in full_life['events']:
        public=project('CandidateEvent',e)
        public['metadata']={k:v for k,v in e['metadata'].items() if k in ['source_id','experience_id','scope','strength']}
        events.append(public)
    eid=next(e['metadata']['experience_id'] for e in events if e['to_state']=='PUBLISHED')
    life={'candidate':project('Candidate',candidate),'events':events,'head':full_life['head'],
          'head_sha256':full_life['head_sha256'],'experience_id':eid,
          'public_proposal':{k:candidate['body'][k] for k in ['title','strategy','public_summary','scope','necessary_conditions','inapplicable_conditions','unknown_fields','limitations']},
          'proposal_authority':'UNTRUSTED_PROPOSAL; Host review supports only the declared scope'}
    emit('lifecycle',life,'g4/demo/CANDIDATE_LIFECYCLE.json')
    rel='g1/live/candidate_origin_02/runs/'+candidate['run_id']
    report=load(rel+'/evaluation_report.json');meta=load(rel+'/runtime_metadata.json');native=load(rel+'/native_rollout_summary.json')
    def ref(raw,timestamp=None):
        p=Path(raw['path']);checkrel=str(p.relative_to(old))
        data=p.read_bytes().splitlines(keepends=True)[raw['line']-1]
        if sha256(data).hexdigest()!=raw['sha256']:raise ValueError('Native reference byte mismatch')
        return {'artifact':checkrel,'line':raw['line'],'sha256':raw['sha256'],'timestamp':timestamp,'included':'NOT_INCLUDED_RAW_LOG'}
    children=[]
    for child in native['subagents']['agents']:
        if not child['verified'] or not child['completed']:raise ValueError('Native own-child verification incomplete')
        children.append({'agent_id':child['agent_id'],'agent_path':child['agent_path'],'parent_thread_id':child['parent_thread_id'],
            'verified':child['verified'],'completed':child['completed'],
            'spawn':ref(child['spawn']['raw_reference'],child['spawn']['timestamp']),
            'completion':ref(child['completion']['raw_reference'],child['completion']['timestamp']),
            'parent_receipt':ref(child['parent_receipt']['communication_reference'])})
    epoch=load('release-g1-scope-sdk-epoch2/SOURCE_MANIFEST.json')
    sv=next(n['public'] for n in g['nodes'] if n['label']=='SourceVerification' and n['public'].get('candidate_id')==candidate['id'])
    origin={'run_id':candidate['run_id'],'session_id':meta['session_id'],'started_at':meta['started_at'],'ended_at':meta['ended_at'],
            'source_commit':epoch['commit'],'source_tree':epoch['git_tree'],'runtime_status':meta['runtime_result'],
            'patch_sha256':report['submission']['sha256'],'candidate_body_sha256':candidate['body_sha256'],
            'source_verification_id':sv['id'],'outcome_id':sv['outcome_id'],'children':children,
            'pytest_exit_code':report['pytest_exit_code'],
            'test_counts':{k:report['test_results'][k] for k in ['collected','passed','failed','errors','skipped']},
            'test_identity_disclosure':'NOT_INCLUDED_PRIVATE_SUITE','authority':'VERIFIED_WITHIN_RECORDED_SCOPE',
            'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN'}
    emit('origin',origin,rel+'/evaluation_report.json')
    readback=load('g1/readback/publication_01/RESULT.json');emit('readback',readback,'g1/readback/publication_01/RESULT.json')
    views=load('g4/demo/WHEN_WHY.json')
    views={k:[decision_view(row) for row in v['candidates']] for k,v in views.items()}
    emit('views',views,'g4/demo/WHEN_WHY.json')
    base='g3/graph-checks/necessity_01/'
    ablation=load(base+'graph_ablation_changes_current_why.json'); restored=load(base+'actual_edge_restore_restores_why.json')
    snapshots=load(base+'only_one_real_edge_removed.json');selected=load(base+'SELECTED_EDGE.json')
    replay=load(base+'ablation_old_snapshot_remains_historical.json');ctrl=selected['path']['path'][0]
    def graph_snapshot(s):
        return {'nodes':[{'label':n[0][0],'id':n[1],'stored_payload_sha256':n[2]} for n in s['nodes']],
                'edges':[dict(zip(['source','relation','id','stored_payload_sha256','target'],e)) for e in s['edges']]}
    before_graph=graph_snapshot(snapshots['before']);after_graph=graph_snapshot(snapshots['after'])
    edge=next(e for e in before_graph['edges'] if e['id']==selected['edge_rows'][0][0])
    def actual_view(resolution):
        row=next(x for x in resolution['candidates'] if x['experience_id']==ctrl)
        return decision_view(row,resolution['query_id'],resolution['query_snapshot_ids'][ctrl])
    rawpath=old/(base+'trusted_graph_commands.jsonl')
    if digest(rawpath)!=frozen[base+'trusted_graph_commands.jsonl']:raise ValueError('Frozen raw queries differ')
    queries=[]
    for line,raw in enumerate(rawpath.read_bytes().splitlines(keepends=True),1):
        x=json.loads(raw);cmd=x['command']
        if len(cmd)<3 or cmd[0] not in ['GRAPH.QUERY','GRAPH.RO_QUERY']:continue
        statement=cmd[2]
        if edge['id'] not in statement:continue
        queries.append({'id':'h3-query-line-'+str(line),'line':line,'line_sha256':sha256(raw).hexdigest(),
            'cypher':statement,'status':x['status'],'started_at':x['started_at'],'ended_at':x['ended_at'],
            'operation':cmd[0],'raw_artifact':base+'trusted_graph_commands.jsonl','raw_included':False})
    sources[base+'trusted_graph_commands.jsonl']=digest(rawpath)
    emit('queries',{'queries':queries,'disclosure':'Only statements involving the actual selected PUBLIC relationship; raw responses/logs NOT_INCLUDED'},base+'trusted_graph_commands.jsonl')
    delete=next(q for q in queries if 'DELETE r' in q['cypher'])
    restore=next(q for q in queries if q['line']>delete['line'] and 'MERGE' in q['cypher'] and q['operation']=='GRAPH.QUERY')
    evolution={'classification':'MAINTAINER_CONTROLLED_ABLATION','agent_outcome_id':None,'experience_id':ctrl,
        'before':actual_view(ablation['before']),'after':actual_view(ablation['after']),'restored':actual_view(restored['resolution']),
        'historical_replay':{k:replay[k] for k in ['query_snapshot_id','retrieval_snapshot_sha256','snapshot_mode']},
        'before_graph':before_graph,'after_graph':after_graph,'selected_edge':edge,
        'delete_query_id':delete['id'],'restore_query_id':restore['id'],'captured_at':delete['ended_at'],
        'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN'}
    emit('evolution',evolution,base+'graph_ablation_changes_current_why.json')
    gov_rel='g2/external/governance_02/runs/c8a6a7ae-fb65-4b2d-98ea-0651eb939a7b/external_report.json'
    raw_rel='g3/external/raw_01/runs/f4406efc-d94d-4d21-b30f-d350248f3d4e/external_report.json'
    # Preserve exact original public outcomes. Public receipt shape is checked
    # by the verifier; no Hidden Oracle is added to an ordinary engineering run.
    gov=load(gov_rel);raw=load(raw_rel)
    def public_result(report,report_rel):
        receipt_rel=str(Path(report_rel).parent/'public-tests/command.json');receipt=load(receipt_rel)
        if sources[receipt_rel]!=report['public_test_receipt_sha256']:raise ValueError('Original public test receipt binding mismatch')
        log=old/Path(receipt_rel).parent/'stderr.log';data=log.read_bytes()
        if digest(log)!=frozen[str(log.relative_to(old))] or sha256(data).hexdigest()!=receipt['stderr_sha256']:raise ValueError('Public test log hash mismatch')
        text=data.decode('utf-8');tests=re.findall(r'^(test_\S+) \(([^\n]+)\) \.\.\. ok$',text,re.MULTILINE)
        count=re.findall(r'^Ran (\d+) tests? in ',text,re.MULTILINE)
        if receipt['exit_code']!=0 or report['public_test_command_exit']!=0 or len(count)!=1 or int(count[0])!=len(tests) or not text.rstrip().endswith('OK'):
            raise ValueError('Actual public tests are incomplete')
        return {'run_id':report['run_id'],'session_id':report['thread_id'],'passed':len(tests),
                'public_test_identities':[group+'::'+name for name,group in tests],
                'exit_code':receipt['exit_code'],'source_report_sha256':sources[report_rel],
                'public_test_receipt_sha256':sources[receipt_rel],'stderr_sha256':sha256(data).hexdigest(),
                'submission_sha256':report['submission_sha256'],'verified_outcome_count':report['verified_outcome_count'],
                'baseline_tree_sha256':report['baseline_tree_sha256']}
    failed=load('g2/external/governance_01/runs/af26fb0c-865d-472c-97e3-c2a2c73fd597/external_report.json')
    pilot={'governance':public_result(gov,gov_rel),'raw_memory':public_result(raw,raw_rel),
           'authority':'EXTERNAL_UNVERIFIED','verified_outcomes':gov['verified_outcome_count']+raw['verified_outcome_count'],'causal_benefit':'UNKNOWN',
           'failed_attempt_run_id':failed['run_id'],'failed_attempt_status':failed['failure_kind'],
           'limitation':'One successful paired pilot, different runtime overhead; no statistical/causal benefit claim.'}
    emit('pilot',pilot,gov_rel)
    def case(identity,title,classification):
        return {'case_id':identity,'title':title,'classification':classification,'visibility':'PUBLIC','mode':'REPLAY',
            **{k:None for k in ['run_id','session_id','candidate_id','experience_id','rule_id','decision_id','query_snapshot_id','outcome_id']},
            'source_commit':None,'source_tree':None,'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN'}
    ca=case('case-a','An Experience Is Born','VERIFIED_WITHIN_RECORDED_SCOPE')
    ca.update(evidence_level='VERIFIED',run_id=origin['run_id'],session_id=origin['session_id'],candidate_id=candidate['id'],experience_id=eid,
        outcome_id=origin['outcome_id'],rule_id=next(x for x in views['bounded_source'] if x['experience_id']==eid)['rule_ids'][0],
        source_commit=origin['source_commit'],source_tree=origin['source_tree'],captured_at=full_life['events'][-1]['created_at'],artifacts=['origin','lifecycle','readback','graph'])
    cb=case('case-b','A Memory Is Challenged','SUPPORTING_CONTROLLED_APPLICABILITY')
    cb.update(evidence_level='SUPPORTING',experience_id='experience:process-local-reservation-lock',rule_id='rule:process-local-lock:1',artifacts=['views','graph'],captured_at=load('g4/demo/MANIFEST.json')['observed_at'],
        missing_identity_reason='Read-only resolver view; no new Agent Session or persisted Decision/QuerySnapshot')
    cc=case('case-c','Knowledge Evolves','SUPPORTING_MAINTAINER_CONTROLLED_ABLATION')
    cc.update(evidence_level='SUPPORTING',run_id=ablation['before']['run_id'],experience_id=ctrl,rule_id=evolution['before']['rule_ids'][0],query_snapshot_id=evolution['before']['query_snapshot_id'],
        captured_at=evolution['captured_at'],artifacts=['evolution','queries'],missing_identity_reason='Host controlled replica experiment; not an Agent Session/Outcome. Exact execution source commit unavailable.')
    claims=[{'id':i,'artifact':artifact,'maximum_statement':text,'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN'} for i,artifact,text in [
        ('birth','origin','The untouched submitted patch passed an independent Oracle in the recorded scope; Host published a bounded proposal.'),
        ('challenge','views','Actual Core recommendations differ when material concurrency facts conflict. This does not prove Agent action changed.'),
        ('evolution','evolution','In a maintainer-controlled replica, deleting one actual supporting edge changed the current recommendation; historical retrieval remained unchanged.'),
        ('external-comparison','pilot','Both actual ordinary project conditions passed seven original public tests; neither is a VerifiedOutcome and no causal benefit is established.')]]
    contract={'schema_version':'aevora.hero/1.0','mode':'REPLAY','visibility':'PUBLIC','source_archive':old.name,
        'captured_at':load('g4/demo/MANIFEST.json')['observed_at'],'same_experience_across_acts':False,
        'causal_benefit':'UNKNOWN','agent_adoption':'UNKNOWN','acts':[ca,cb,cc],'artifacts':artifacts,'claims':claims,
        'not_included':['Hidden Tests and Oracle source','Private Manifest and Reference Patches','Raw model/MCP logs and private native task content','Host credentials and individual secret fingerprints','Unavailable Act II persisted IDs and Act III execution source commit'],
        'trust':'PUBLIC projections from frozen local artifacts; externally pin this contract. Local consistency, no external attestation.'}
    write(root/'hero_scenario_contract.json',contract)
    (a/'g0'/receipt_label).mkdir();write(a/'g0'/receipt_label/'PROJECTION_SOURCES.json',{'source_files':sources,'contract_sha256':digest(root/'hero_scenario_contract.json'),'at':now()})
    print(json.dumps({'contract_sha256':digest(root/'hero_scenario_contract.json'),'artifacts':len(artifacts),'status':'CREATED_NOT_YET_VERIFIED'}))


def demo(root,expected):
    from examples.observatory.verify_hero import verify
    receipt=verify(root,expected)
    contract=json.loads((root/'hero_scenario_contract.json').read_text())
    print(json.dumps({'verification':receipt,'acts':contract['acts'],'claims':contract['claims']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=['build','demo']);p.add_argument('--root',type=Path,default=ROOT/'examples/observatory');p.add_argument('--sha256');p.add_argument('--receipt-label',default='hero');args=p.parse_args()
    if args.op=='build':build(args.root,args.receipt_label)
    else:demo(args.root,args.sha256)
