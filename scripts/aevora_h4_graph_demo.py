"""Actual controlled support-edge intervention in an owned current-graph replica."""
import argparse,json,uuid
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now

def main(label):
    from aevora.graph_repository import GraphRepository
    from aevora.experience_resolver import ExperienceResolver
    from aevora_observatory.projection import CONTEXTS
    from examples.observatory.public_projection import decision_view
    a=archive();out=a/'g4'/label;out.mkdir(mode=0o700)
    source=GraphRepository.from_environment();before_source=source.state_fingerprint();name='aevora_h4_control_'+uuid.uuid4().hex;source._graph.copy(name)
    import os
    os.environ['AEVORA_FALKORDB_GRAPH']=name;repo=GraphRepository.from_environment()
    edge=json.loads((ROOT/'examples/observatory/replay/evolution.json').read_text())['selected_edge'];eid='experience:sqlite-atomic-reservation'
    commands=[]
    def query(statement,params,readonly=True):
        at=now();value=repo.query(statement,params,read_only=readonly);commands.append({'cypher':statement,'params':params,'rows':value,'read_only':readonly,'started_at':at,'ended_at':now()});return value
    def current():return decision_view(next(c for c in ExperienceResolver(repo).resolve(CONTEXTS['workers'],persist_snapshots=False)['candidates'] if c['experience_id']==eid))
    try:
        before=current();snapshots=query('MATCH(n:QuerySnapshot) RETURN n.id,n.payload_sha256 ORDER BY n.id',{})
        rows=query('MATCH(s)-[r:VERIFIES {id:$id}]->(t) RETURN s.id,t.id,r.payload_json,r.payload_sha256',{'id':edge['id']});assert len(rows)==1
        s,t,payload,fingerprint=rows[0];assert s==edge['source'] and t==edge['target']
        deleted=query('MATCH()-[r:VERIFIES {id:$id}]->() DELETE r RETURN count(r)',{'id':edge['id']},False);assert deleted==[[1]]
        after=current();assert before['decision']=='APPLY' and after['decision']=='VERIFY' and len(before['support_paths'])>0 and after['support_paths']==[]
        restored_row=query('MATCH(s:Evidence {id:$source}),(t:VerifiedOutcome {id:$target}) MERGE(s)-[r:VERIFIES {id:$id}]->(t) ON CREATE SET r.payload_json=$payload,r.payload_sha256=$sha RETURN r.payload_sha256',{'source':s,'target':t,'id':edge['id'],'payload':payload,'sha':fingerprint},False);assert restored_row==[[fingerprint]]
        restored=current();assert restored==before
        assert query('MATCH(n:QuerySnapshot) RETURN n.id,n.payload_sha256 ORDER BY n.id',{})==snapshots
        write(out/'RESULT.json',{'status':'PASS','classification':'MAINTAINER_CONTROLLED_ABLATION','actual_replica_graph':name,'source_fingerprint_before':before_source,'before':before,'after':after,'restored':restored,'selected_edge':edge,'queries':commands,'historical_snapshots_unchanged':True,'agent_run_id':None,'agent_outcome_id':None,'causal_benefit':'UNKNOWN','at':now()})
    finally:repo._graph.delete();repo.close();assert source.state_fingerprint()==before_source;source.close()
    print(json.dumps({'status':'PASS','decisions':[before['decision'],after['decision'],restored['decision']],'support_paths':[len(v['support_paths']) for v in [before,after,restored]],'new_agent_outcomes':0}));return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);args=p.parse_args();raise SystemExit(main(args.label))
