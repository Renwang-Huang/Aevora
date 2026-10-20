"""Actual official MCP/STDIO over owned scoped transport; no model request."""
from pathlib import Path
import json,sys,uuid,secrets,tempfile,os
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.historical_import import public_context
from aevora.mcp_broker import MCPBroker
from scripts.aevora_h2_security import RPCClient
out=E/'01_c1_repairs/mcp-wire';out.mkdir()
main=GraphRepository.from_environment();name='aevora_v5c_wire_'+uuid.uuid4().hex;main._graph.copy(name);main.close();os.environ['AEVORA_FALKORDB_GRAPH']=name
repo=GraphRepository.from_environment();checks=[]
def check(n,value,detail):
 checks.append({'name':n,'status':'PASS' if value else 'FAIL','detail':detail,'at':now()})
 with (out/'checks.jsonl').open('a') as f:f.write(json.dumps(checks[-1])+'\n')
 if not value:raise AssertionError(n)
try:
 with tempfile.TemporaryDirectory(prefix='v5c-wire-') as d:
  token=secrets.token_hex(32)
  b=MCPBroker(run_id='v5c-wire-'+uuid.uuid4().hex,public_context=public_context('multi_process_shared_sqlite'),socket_path=Path(d)/'mcp.sock',run_token=token,event_path=out/'raw_mcp.jsonl',enable_proposals=True)
  with b:
   c=RPCClient(b,token,out/'raw_client.jsonl');c.initialize()
   try:
    catalog=c.call('tools/list');write(E/'01_c1_repairs/MCP_TOOLS_LIST.json',catalog)
    names={t['name'] for t in catalog['result']['tools']};check('actual_four_tool_catalog',names=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'},sorted(names))
    q=c.tool('resolve_experience',{'task_context':{}});check('actual_empty_context_query',not q['result'].get('isError'),q)
    qid=q['result']['structuredContent']['query_id'];eid=q['result']['structuredContent']['candidates'][0]['experience_id']
    before=repo.state_fingerprint()
    for label,args in [('list',{'worker_count_known':[2,4]}),('nested',{'concurrency_scope':{'value':'independent_processes'}}),('unsupported',{'task_id':'D'}),('conflict',{'concurrency_scope':'untrusted-conflicting-value'})]:
     r=c.tool('resolve_experience',{'task_context':args});check(label+'_rejected',r['result'].get('isError') is True,r)
     check(label+'_graph_unchanged',repo.state_fingerprint()==before,repo.state_fingerprint())
    bad=c.tool('build_evidence_bundle',{'experience_id':eid,'query_id':'query:foreign-run:missing'});check('foreign_query_rejected',bad['result'].get('isError') is True,bad)
    bad=c.tool('record_decision',{'decision':{'query_id':qid,'experience_id':eid,'decision':'APPLY','reason':'Explicit Host negative control','verified':True}});check('forged_outcome_authority_rejected',bad['result'].get('isError') is True,bad)
    check('no_truth_mutation_by_negative_calls',repo.state_fingerprint()==before,repo.state_fingerprint())
   finally:c.close()
  write(out/'CLEANUP.json',b.metadata)
 # Real connection refusal through the actual SDK server, not a fake GraphUnavailable.
 previous=os.environ['AEVORA_FALKORDB_PORT'];os.environ['AEVORA_FALKORDB_PORT']='17709'
 try:
  with tempfile.TemporaryDirectory(prefix='v5c-wire-offline-') as d:
   token=secrets.token_hex(32);b=MCPBroker(run_id='v5c-offline-'+uuid.uuid4().hex,public_context={},socket_path=Path(d)/'mcp.sock',run_token=token,event_path=out/'offline_mcp.jsonl')
   with b:
    c=RPCClient(b,token,out/'offline_client.jsonl');c.initialize()
    try:
     r=c.tool('resolve_experience',{'task_context':{}})
     check('actual_db_connection_refusal_not_fallback',r['result'].get('isError') is True and 'AEVORA_GRAPH_UNAVAILABLE' in r['result']['content'][0]['text'],r)
    finally:c.close()
 finally:os.environ['AEVORA_FALKORDB_PORT']=previous
 write(out/'RESULT.json',{'status':'PASS','checks':checks,'model_requests':0,'scope':'TRUSTED_HOST_REAL_MCP_CONTRACT_CONTROL; no Agent decision/adoption claimed'})
finally:repo._graph.delete();repo.close()
print('C1_REAL_WIRE_PASS',len(checks))
