"""Owned actual database outage/restart; full live graph is never pruned."""
from pathlib import Path
import sys,json,tempfile,secrets,time
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.checkpoint import capture_graph,save_boundary
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.mcp_broker import MCPBroker
from scripts.aevora_h2_security import RPCClient
out=E/'05_graph/db_outage';out.mkdir(exist_ok=True);mode=sys.argv[1]
if mode=='offline':
 with tempfile.TemporaryDirectory(prefix='v5c-offline-') as d:
  token=secrets.token_hex(32);b=MCPBroker(run_id='v5c-actual-db-offline',public_context={},socket_path=Path(d)/'mcp.sock',run_token=token,event_path=out/'offline_mcp.jsonl')
  with b:
   c=RPCClient(b,token,out/'offline_client.jsonl');c.initialize()
   try:
    result=c.tool('resolve_experience',{'task_context':{}})
    ok=result['result'].get('isError') is True and 'AEVORA_GRAPH_UNAVAILABLE' in result['result']['content'][0]['text']
    write(out/'offline_result.json',{'status':'PASS' if ok else 'FAIL','actual_result':result,'expected':'Explicit real DB unavailable, no static fallback','model_requests':0,'at':now()});assert ok
   finally:c.close()
  write(out/'offline_cleanup.json',b.metadata)
else:
 errors=[]
 for attempt in range(30):
  try:
   r=GraphRepository.from_environment();r.state_fingerprint();break
  except Exception as error:errors.append({'attempt':attempt,'error_type':type(error).__name__});time.sleep(.2)
 else:raise RuntimeError('Owned DB startup did not become healthy')
 try:
  graph=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/(mode+'_graph.json'),graph)
  boundary=save_boundary(r,writers_quiesced=True,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/(mode+'_save_boundary.json'),boundary)
  if mode=='after':
   before=json.loads((out/'before_graph.json').read_text());ok=graph==before
   write(out/'RESULT.json',{'status':'PASS' if ok else 'FAIL','full_live_graph_exact_restoration':ok,'graph_before':before['graph_sha256'],'graph_after':graph['graph_sha256'],'node_count':graph['node_count'],'edge_count':graph['edge_count'],'startup_observations':errors,'scope':'Actual same owned container graceful RDB SAVE/stop/start, not crash/AOF recovery','model_requests':0,'at':now()});assert ok
 finally:r.close()
print('DB_PROBE',mode,'PASS')
