"""Late diagnostic replay of pinned PRE-FIX source, never a new model challenge."""
from pathlib import Path
import sys,os,json,tempfile,secrets,uuid,hashlib
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.mcp_broker import MCPBroker,MAX_MESSAGE_BYTES
from aevora.historical_import import public_context
from scripts.aevora_h2_security import RPCClient
out=E/'01_root_cause/exact_old_broker_replay';out.mkdir()
os.environ['AEVORA_FALKORDB_GRAPH']='aevora_v5c_live_0a70f0ccc4204a75846e00199c2923c0';r=GraphRepository.from_environment();original=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);assert original['graph_sha256']=='ad8d4c6fbe7b72d2093d08236f42a325b6221a929bdb08f4bafa0c057aa2c21d';name='aevora_v5c1_exactold_'+uuid.uuid4().hex;r._graph.copy(name);r.close();os.environ['AEVORA_FALKORDB_GRAPH']=name
with tempfile.TemporaryDirectory(prefix='v5c1-exact-') as td:
 token=secrets.token_hex(32);b=MCPBroker(run_id='v5c1-exact-old-'+uuid.uuid4().hex,public_context=public_context('multi_process_shared_sqlite'),socket_path=Path(td)/'mcp.sock',run_token=token,event_path=out/'mcp.jsonl',enable_proposals=True,server_command=[sys.executable,'-u',str(E/'old_sdk_capture_wrapper.py')])
 with b:
  c=RPCClient(b,token,out/'client.jsonl');c.initialize()
  try:reply=c.tool('resolve_experience',{'task_context':{}})
  finally:c.close()
 frames=(out/'exact_sdk_stdout.jsonl').read_bytes().splitlines(keepends=True);frame=next(raw for raw in frames if json.loads(raw).get('id')==2);obj=json.loads(frame);body=obj['result'];assert reply is None and b.metadata['rejections'].get('MESSAGE_SIZE_LIMIT')==1 and len(frame)>MAX_MESSAGE_BYTES
 write(out/'RESULT.json',{'status':'EXPECTED_LEGACY_FAIL_REPRODUCED','at':now(),'measurement_scope':'ACTUAL EXACT SDK FRAME CAPTURED BEFORE FORWARDING INTO UNCHANGED PUBLIC BROKER','replay_timing':'POST_FIX_DIAGNOSTIC_USING_PINNED_PRE_FIX_SERVER_SOURCE; does not replace original first G1 receipt','baseline_server_sha256':sha(E/'01_root_cause/baseline_mcp_server.py'),'baseline_commit':'f016a825be67c0d30c8dcdb7f6b046c26d65ca95','wire_utf8_bytes':len(frame),'wire_sha256':hashlib.sha256(frame).hexdigest(),'limit_bytes':MAX_MESSAGE_BYTES,'full_graph_sha256':original['graph_sha256'],'full_graph_nodes':original['node_count'],'full_graph_edges':original['edge_count'],'sdk_text_equals_structured':json.loads(body['content'][0]['text'])==body['structuredContent'],'candidate_count':len(body['structuredContent']['candidates']),'actual_public_broker_rejection':b.metadata['rejections'],'broker_limit_unchanged':True,'bounded_trusted_capture_limit_bytes':8*1024*1024,'no_edges_removed':True,'model_requests':0});write(out/'cleanup.json',b.metadata)
 print('EXACT_PRE_FIX_BROKER_FRAME',len(frame),hashlib.sha256(frame).hexdigest(),flush=True)
