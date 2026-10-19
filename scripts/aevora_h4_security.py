"""Reuse actual mature three-layer probes plus typed proposal controls for H4."""
import os
import uuid
from scripts.aevora_h4_audit import archive


def main(label='security'):
    from scripts.aevora_h2_security import Evidence,physical_probes,broker_case,RPCClient
    from aevora.graph_repository import GraphRepository
    from aevora.candidate import CandidateLifecycle
    from aevora_core.tests.test_h3_lifecycle import proposal,FACTS
    if os.environ['AEVORA_FALKORDB_PORT']!='17692':raise ValueError('Only newly owned H4 endpoint')
    e=Evidence(archive()/'g1'/label);physical_probes(e)
    previous=os.environ['AEVORA_FALKORDB_GRAPH'];os.environ['AEVORA_FALKORDB_GRAPH']='aevora_h4_security_'+uuid.uuid4().hex
    repo=GraphRepository.from_environment();CandidateLifecycle(repo).initialize()
    try:
        with broker_case(e,'proposal_mcp',context=FACTS,enable_proposals=True) as (broker,token,d):
            c=RPCClient(broker,token,d/'client.jsonl');c.initialize()
            tools=c.call('tools/list')['result']['tools'];e.check('four_public_tools',{t['name'] for t in tools}=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'},tools,scope='Actual official SDK catalogue')
            r=c.tool('resolve_experience',{'task_context':{}});e.check('actual_empty_graph',r['result']['structuredContent']['candidates']==[],r,scope='Actual fresh graph; no fallback')
            p=proposal('h4-explicit-security-control');r=c.tool('propose_experience',{'proposal':p});v=r['result']['structuredContent']
            e.check('proposal_stays_untrusted',v['status']=='PROPOSED_UNTRUSTED' and repo.experience_ids()==[],v,scope='Explicit untrusted negative fixture; no model outcome')
            for field,value in [('verified',True),('run_id','foreign'),('source_type','natural_agent_run')]:
                r=c.tool('propose_experience',{'proposal':{**p,field:value}});e.check('deny_claim_'+field,r['result']['isError'] is True,r,scope='Real SDK authority denial')
            bad={**p,'candidate_key':'foreign-ref','source_references':[{'kind':'Query','id':'query:foreign'}]};r=c.tool('propose_experience',{'proposal':bad});e.check('foreign_reference',r['result']['isError'] is True,r,scope='Actual same-run reference enforcement');c.close()
            for tool in ['publish','admit','withdraw','submit_outcome','cypher']:
                c=RPCClient(broker,token,d/('deny-'+tool+'.jsonl'));c.initialize();r=c.tool(tool,{})
                e.check('privileged_'+tool,r is None or 'error' in r,r,scope='Broker excludes Host authority');c.close()
            c=RPCClient(broker,token,d/'wrong-run.jsonl',run_id='foreign');e.check('cross_run_capability',c.ack.get('aevora_transport')!='READY',c.ack,scope='Capability cannot authorize a different Run');c.close()
        e.check('untrusted_source_graph',repo.query('MATCH(n:SourceVerification) RETURN count(n)')==[[0]],repo.state_fingerprint(),scope='No Host verification minted from proposal')
    finally:repo._graph.delete();repo.close();os.environ['AEVORA_FALKORDB_GRAPH']=previous
    return e.finish('H4 actual inherited physical boundary and official proposal SDK')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='security');args=p.parse_args()
    if not args.label.replace('-','').isalnum():raise ValueError('Simple unique label required')
    raise SystemExit(main(args.label))
