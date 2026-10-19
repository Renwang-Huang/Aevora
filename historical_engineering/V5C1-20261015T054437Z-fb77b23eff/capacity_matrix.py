from pathlib import Path
import sys,os,json,uuid,secrets,tempfile,csv
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.mcp_server import ExperienceService
from aevora.historical_import import public_context,ATOMIC_ID
from aevora.mcp_broker import MCPBroker,MAX_MESSAGE_BYTES
from aevora.mcp_projection import wire_bytes
from scripts.aevora_h2_security import RPCClient
out=E/'02_fix/capacity';out.mkdir();base='aevora_v5c_live_0a70f0ccc4204a75846e00199c2923c0';context=public_context('multi_process_shared_sqlite');rows=[]
for label,additional,competitors,empty in [('full_original',0,0,False),('feedback_contract_1',1,0,False),('feedback_contract_3',3,0,False),('feedback_contract_8',8,0,False),('index_64',0,61,False),('index_256',0,253,False),('empty',0,0,True)]:
 os.environ['AEVORA_FALKORDB_GRAPH']=base;main=GraphRepository.from_environment();name='aevora_v5c1_scale_'+uuid.uuid4().hex
 if not empty:main._graph.copy(name)
 main.close();os.environ['AEVORA_FALKORDB_GRAPH']=name;r=GraphRepository.from_environment()
 if empty:r.initialize()
 for i in range(additional):
  key='v5c1-capacity-'+str(i)
  r.attach_evidence(ATOMIC_ID,{'id':'evidence:'+key,'source_type':'synthetic_or_test_fixture','source_run_id':key,'public_summary':'EXPLICIT_SYNTHETIC_FEEDBACK_CAPACITY_CONTRACT; not an Agent outcome'},
   {'id':'outcome:'+key,'run_id':key,'submission_digest':'a'*64,'evaluator_fingerprint':'b'*64,'test_suite_fingerprint':'c'*64,'verifier_identity':'SYNTHETIC_CAPACITY_TEST_ONLY','verdict':'PASS'},
   {'id':'context:'+key,'facts':context},{'id':'task:'+key,'public_title':'Synthetic feedback-growth capacity contract'},relation='OBSERVED_OUTCOME')
 for i in range(competitors):
  key='v5c1-capacity-'+str(i)
  r.import_experience({'id':'experience:'+key,'strategy':'Synthetic scale competitor','title':'Synthetic scale '+str(i),'source_type':'synthetic_or_test_fixture','public_summary':'Capacity fixture only, no Agent outcome','created_at':now()},
   {'id':'rule:'+key,'version':'capacity/1','premises':[{'id':'premise:'+key,'fact_key':'worker_count_known','allowed_values':[True]}]})
 state=r.state_fingerprint();directory=out/label;directory.mkdir()
 full=ExperienceService(run_id='v5c1-scale-direct-'+uuid.uuid4().hex,public_context=context,repository=r).resolve_experience({});write(directory/'unprojected_public_result.json',full)
 expected={v['experience_id']:(v['decision'],v['reason'],v['retrieval_snapshot_sha256'],v['governance_evidence_sha256']) for v in full['candidates']}
 with tempfile.TemporaryDirectory(prefix='v5c1-scale-') as td:
  token=secrets.token_hex(32);b=MCPBroker(run_id='v5c1-scale-'+uuid.uuid4().hex,public_context=context,socket_path=Path(td)/'mcp.sock',run_token=token,event_path=directory/'mcp.jsonl',enable_proposals=True,request_timeout=120)
  with b:
   c=RPCClient(b,token,directory/'client.jsonl');c.channel.settimeout(120);c.initialize()
   try:
    result=c.tool('resolve_experience',{'task_context':{}});assert result and not result['result'].get('isError'),label
    page=result['result']['structuredContent'];allrows=[];pages=0;queryid=page.get('query_id')
    while True:
     allrows+=page['candidates'];pages+=1
     if not page['has_more']:break
     result=c.tool('resolve_experience',{'task_context':{},'cursor':page['next_cursor']});assert result and not result['result'].get('isError'),label
     page=result['result']['structuredContent']
    actual={v['experience_id']:(v['decision'],v['reason'],v['retrieval_snapshot_sha256'],v['governance_evidence_sha256']) for v in allrows}
    assert actual==expected and len(allrows)==len(expected),label
    # Existing full bundle plus full resolver-candidate view through the real SDK.
    for eid in list(expected)[:3]:
     for view in ['bundle','candidate']:
      reply=c.tool('build_evidence_bundle',{'experience_id':eid,'query_id':queryid,'view':view});assert reply and not reply['result'].get('isError'),(label,eid,view)
      detail=reply['result']['structuredContent']
      while detail.get('has_more'):
       reply=c.tool('build_evidence_bundle',{'experience_id':eid,'query_id':queryid,'view':view,'cursor':detail['next_cursor']});assert reply and not reply['result'].get('isError');detail=reply['result']['structuredContent']
   finally:c.close()
  write(directory/'cleanup.json',b.metadata)
 events=[json.loads(line) for line in (directory/'mcp.jsonl').read_text().splitlines()]
 frames=[len(x['raw_json'].encode()) for x in events if x.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and x.get('category')=='JSONRPC']
 assert not b.metadata['rejections'] and max(frames)<MAX_MESSAGE_BYTES
 row={'case':label,'actor':'REAL_SDK_UDS_HOST_CONTROL_NOT_AGENT','synthetic_growth':bool(additional or competitors),'nodes_before':state['node_count'],'edges_before':state['edge_count'],'candidates':len(allrows),'index_pages':pages,'unprojected_worst_id_wire_bytes':len(wire_bytes(full)),'max_actual_public_wire_bytes':max(frames),'frame_count':len(frames),'decisions_and_key_provenance_equal':True,'status':'PASS'}
 rows.append(row);write(directory/'RESULT.json',row);print(label,'PASS',len(allrows),pages,max(frames),flush=True);r.close()
with (E/'02_fix/MCP_PAYLOAD_SIZE_MATRIX.csv').open('x') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
write(out/'RESULT.json',{'status':'PASS','at':now(),'cases':rows,'model_requests':0,'original_full_graph_no_edge_removal':True,'synthetic_capacity_cases_not_actual_host_adoption':True})
