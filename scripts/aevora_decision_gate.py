#!/usr/bin/env python3
"""Capture actual WHEN/WHY responses and graph-only ablations, offline."""
import argparse
import json
import os
from pathlib import Path
import uuid

from aevora.experience_resolver import ExperienceResolver
from aevora.graph_repository import GraphRepository
from aevora.historical_import import ATOMIC_ID, LOCK_ID, public_context


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);args=p.parse_args()
    main=GraphRepository.from_environment()
    responses={label:ExperienceResolver(main).resolve(public_context(topology)) for label,topology in
        [('single_process','single_process_multi_thread'),('independent_workers','multi_process_shared_sqlite'),('unknown_topology_fixture',None)]}
    kinds=lambda row: {c['experience_id']:c['decision'] for c in row['candidates']}
    assert [kinds(responses[k])[LOCK_ID] for k in responses]==['APPLY','ABSTAIN','VERIFY']
    assert kinds(responses['single_process'])[ATOMIC_ID]=='APPLY' and kinds(responses['independent_workers'])[ATOMIC_ID]=='APPLY'
    ablations={}
    for label,query,params in [
        ('remove_support','MATCH (r:ExperienceRevision)-[link:SUPPORTED_BY]->(e:Evidence {id:$id}) DELETE link',{'id':'evidence:history:cf083714-0a91-4392-81ed-1070f2cdef71'}),
        ('remove_required_premise','MATCH (r:Rule)-[link:REQUIRES]->(p:Premise {id:$id}) DELETE link',{'id':'premise:lock:topology'}),
        ('remove_all_experience_edges','MATCH (e:Experience)-[r]->() DELETE r',{})]:
        name='aevora_gate_ablation_'+uuid.uuid4().hex
        main._graph.copy(name)
        old=os.environ['AEVORA_FALKORDB_GRAPH'];os.environ['AEVORA_FALKORDB_GRAPH']=name
        repo=GraphRepository.from_environment();os.environ['AEVORA_FALKORDB_GRAPH']=old
        try:
            context=public_context('single_process_multi_thread' if label=='remove_required_premise' else 'multi_process_shared_sqlite')
            before=ExperienceResolver(repo).resolve(context)
            repo.query(query,params,read_only=False)
            after=ExperienceResolver(repo).resolve(context)
            assert before['graph_snapshot_sha256']!=after['graph_snapshot_sha256']
            target=LOCK_ID if label=='remove_required_premise' else ATOMIC_ID
            assert kinds(after)[target]=='VERIFY'
            ablations[label]={'graph':name,'executed_cypher':query,'parameters':params,'before':before,'after':after}
        finally:repo._graph.delete();repo.close()
    result={'gate':'G2','status':'PASS','responses':responses,'actual_graph_ablations':ablations,
        'main_state':main.state_fingerprint(),'qualification':'Unknown topology is a decision fixture only, no D-v02 business implementation; no causal success claim'}
    main.close()
    with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'gate':'G2','status':'PASS','matrix':{k:kinds(v) for k,v in responses.items()},'actual_graph_ablations':list(ablations)}))
    return 0


if __name__=='__main__':raise SystemExit(main())
