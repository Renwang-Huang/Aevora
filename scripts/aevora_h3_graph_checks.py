"""Finite graph checks on the separately owned H3 cold-restored database.

These are trusted controlled interventions, not additional Agent outcomes.
Actual SDK commands/results are archived; source database is never modified.
"""
import argparse
import json
import os
import uuid
from datetime import datetime,timedelta,timezone
from scripts.aevora_h3_audit import archive,write,now,digest
from scripts.aevora_h2_graph_e2e import RawCommands


def main(label,phase):
    from aevora.graph_repository import GraphRepository
    from aevora.candidate import CandidateLifecycle,ReviewGrant
    from aevora.checkpoint import capture_graph
    from aevora.models import LIFECYCLE_SCHEMA_VERSION
    from aevora.mcp_server import ExperienceService
    from aevora.experience_resolver import ExperienceResolver
    from aevora.historical_import import public_context
    if os.environ.get('AEVORA_FALKORDB_PORT')!='17690':raise ValueError('Only owned H3 cold replica is allowed')
    A=archive(); recovery=json.loads((A/'g1/recovery/lifecycle_02/RESULT.json').read_text())
    if recovery['target_port']!=17690:raise ValueError('Cold replica receipt missing')
    out=A/('g1' if phase=='lifecycle' else 'g3')/'graph-checks'/label;out.mkdir(parents=True,mode=0o700)
    repo=GraphRepository.from_environment(); raw=RawCommands(out);raw.attach(repo)
    checks=[]
    def check(name,value,data):
        checks.append({'name':name,'status':'PASS' if value else 'FAIL','actual':data,'at':now()})
        write(out/(name+'.json'),data)
        if not value:raise ValueError('Actual graph check failed: '+name)
    try:
        life=CandidateLifecycle(repo)
        before=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'BEFORE.json',before)
        publication=json.loads((A/'g1/review/origin02/RESULT.json').read_text())['candidates'][0]
        cid=publication['candidate_id'];eid=publication['experience_id']
        original=life.inspect(cid)
        source_id=next(e['metadata']['source_id'] for e in original['events'] if e['to_state']=='ADMITTED_BOUNDED')
        facts=repo.get_node('SourceVerification',source_id)['facts']
        if phase=='lifecycle':
            check('actual_cold_restored_published_chain',original['head']['state']=='PUBLISHED',original)
            svc=ExperienceService(run_id='h3-replica-observation-'+uuid.uuid4().hex,public_context=facts,repository=repo)
            resolved=svc.resolve_experience({});bundle=svc.build_evidence_bundle(eid,resolved['query_id'])
            check('positive_bounded_source',next(x for x in resolved['candidates'] if x['experience_id']==eid)['decision']=='APPLY',resolved)
            write(out/'BUNDLE_BEFORE.json',bundle)
            body=dict(original['candidate']['body']);body['candidate_key']='controlled-no-evidence';body['source_references']=[]
            body['public_summary']='EXPLICIT HOST NEGATIVE FIXTURE: self-reported tests do not establish a trusted outcome.'
            bad=life.propose('h3-explicit-negative-fixture',body);bad_id=bad['candidate_id']
            grant=ReviewGrant('h3-replica-host-controller',(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat())
            def move(target,state,key,reason):
                return life.transition(target,state,expected_head_sha256=life.inspect(target)['head_sha256'],event_key=key,reason=reason,grant=grant)
            move(bad_id,'EVIDENCE_PENDING','pending','No independently verified source; explicitly controlled fixture')
            check('unverified_fixture_excluded',bad_id not in repo.experience_ids() and life.inspect(bad_id)['head']['state']=='EVIDENCE_PENDING',life.inspect(bad_id))
            move(bad_id,'REJECTED','reject','Self-reported PASS is not a trusted Outcome')
            check('negative_rejection_retained',life.inspect(bad_id)['head']['state']=='REJECTED',life.inspect(bad_id))
            move(cid,'WITHDRAWN','replica-controlled-withdrawal','Controlled withdrawal only in cold replica; production publication remains unchanged')
            after=svc.resolve_experience({});replay=svc.build_evidence_bundle(eid,resolved['query_id'])
            check('withdrawal_changes_future_query',eid not in {x['experience_id'] for x in after['candidates']},after)
            check('old_query_snapshot_replays',replay['snapshot_mode']=='IMMUTABLE_QUERY_REPLAY' and replay['retrieval_snapshot_sha256']==bundle['retrieval_snapshot_sha256'],replay)
            check('withdrawal_retains_candidate_events',life.inspect(cid)['head']['state']=='WITHDRAWN' and len(life.inspect(cid)['events'])==len(original['events'])+1,life.inspect(cid))
            saved=repo._client.connection.save();check('actual_save_after_withdrawal',saved is True,{'save_response':saved,'endpoint_port':17690})
        else:
            contexts={'single_process':public_context('single_process_threads'),'independent_processes':public_context('multi_process_shared_sqlite')}
            resolutions={k:ExperienceResolver(repo).resolve(v,persist_snapshots=False) for k,v in contexts.items()}
            positives=[x for r in resolutions.values() for x in r['candidates'] if x['decision']=='APPLY' and x.get('principle_support_paths')]
            negatives=[x for x in resolutions['independent_processes']['candidates'] if x.get('conflicting_premises') and x['decision']!='APPLY']
            check('positive_and_negative_transfer_actual_facts',bool(positives) and bool(negatives),resolutions)
            row=positives[0];path=row['principle_support_paths'][0];eid=row['experience_id']
            context=next(contexts[k] for k,r in resolutions.items() if row in r['candidates'])
            svc=ExperienceService(run_id='h3-necessity-'+uuid.uuid4().hex,public_context=context,repository=repo)
            actual_before=svc.resolve_experience({});bundle=svc.build_evidence_bundle(eid,actual_before['query_id'])
            evidence=path['records']['Evidence']['id']; outcome=path['records']['VerifiedOutcome']['id']
            edges=repo.query('MATCH(s:Evidence {id:$s})-[r:VERIFIES]->(t:VerifiedOutcome {id:$t}) RETURN r.id,r.payload_json,r.payload_sha256',{'s':evidence,'t':outcome})
            if len(edges)!=1:raise ValueError('Selected material edge is not unique')
            write(out/'SELECTED_EDGE.json',{'path':path,'edge_rows':edges})
            pre=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION)
            repo.query('MATCH(s:Evidence {id:$s})-[r:VERIFIES {id:$id}]->(t:VerifiedOutcome {id:$t}) DELETE r',{'s':evidence,'t':outcome,'id':edges[0][0]},read_only=False)
            ablated=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION)
            check('only_one_real_edge_removed',ablated['nodes']==pre['nodes'] and len(ablated['edges'])==len(pre['edges'])-1,{'before':pre,'after':ablated})
            current=svc.resolve_experience({});new_bundle=svc.build_evidence_bundle(eid,current['query_id'])
            check('graph_ablation_changes_current_why',path in bundle['support_paths'] and path not in new_bundle['support_paths'] and bundle['retrieval_snapshot_sha256']!=new_bundle['retrieval_snapshot_sha256'],{'before':actual_before,'after':current,'bundle_before':bundle,'bundle_after':new_bundle})
            replay=svc.build_evidence_bundle(eid,actual_before['query_id'])
            check('ablation_old_snapshot_remains_historical',replay['retrieval_snapshot_sha256']==bundle['retrieval_snapshot_sha256'],replay)
            repo.put_edge('VERIFIES','Evidence',evidence,'VerifiedOutcome',outcome,json.loads(edges[0][1]))
            restored=svc.resolve_experience({});restored_bundle=svc.build_evidence_bundle(eid,restored['query_id'])
            check('actual_edge_restore_restores_why',path in restored_bundle['support_paths'] and restored_bundle['retrieval_snapshot_sha256']==bundle['retrieval_snapshot_sha256'],{'resolution':restored,'bundle':restored_bundle})
        write(out/'AFTER.json',capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION))
        result={'status':'PASS','checks':checks,'phase':phase,'port':17690,'graph':repo.graph_name,'source_port':17689,'classification':'REAL_CONTROLLED_INTERVENTION_ON_COLD_REPLICA; NOT_NEW_AGENT_OUTCOME','causal_benefit':'UNKNOWN','at':now()}
        write(out/'RESULT.json',result);print(json.dumps({'status':'PASS','checks':len(checks),'phase':phase}));return 0
    finally:
        raw.close();repo.close();write(out/'RAW_RECEIPT.json',{'sha256':digest(raw.path),'commands':raw.count})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);p.add_argument('--phase',choices=['lifecycle','necessity'],required=True)
    a=p.parse_args();raise SystemExit(main(a.label,a.phase))
