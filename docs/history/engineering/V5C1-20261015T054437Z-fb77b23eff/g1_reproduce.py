from pathlib import Path
import os,sys,json,uuid,tempfile,secrets,subprocess,select,time,hashlib,collections
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.mcp_broker import MCPBroker,MAX_MESSAGE_BYTES
from aevora.historical_import import public_context
from scripts.aevora_h2_security import RPCClient
out=E/'01_root_cause';cfg=json.loads((E/'CONFIG.json').read_text());O=Path(cfg['old_full'])
name='aevora_v5c_live_0a70f0ccc4204a75846e00199c2923c0';os.environ['AEVORA_FALKORDB_GRAPH']=name
repo=GraphRepository.from_environment();before=capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION)
expected=json.loads((E/'00_baseline/HISTORICAL_FULL_GRAPH.json').read_text())
write(out/'FULL_GRAPH_RESTORED.json',{'at':now(),'full_snapshot_equal':before==expected,'graph':before,'historical_source_sha256':hashlib.sha256((E/'00_baseline/HISTORICAL_FULL_GRAPH.json').read_bytes()).hexdigest()});assert before==expected
# Preserve the exact restored graph; each probe uses a complete independent copy.
copyname='aevora_v5c1_prefx_wire_'+uuid.uuid4().hex;repo._graph.copy(copyname);os.environ['AEVORA_FALKORDB_GRAPH']=copyname
with tempfile.TemporaryDirectory(prefix='v5c1-before-') as d:
 token=secrets.token_hex(32);b=MCPBroker(run_id='v5c1-before-'+uuid.uuid4().hex,public_context=public_context('multi_process_shared_sqlite'),socket_path=Path(d)/'mcp.sock',run_token=token,event_path=out/'before_mcp.jsonl',enable_proposals=True)
 with b:
  c=RPCClient(b,token,out/'before_client.jsonl');c.initialize()
  try:
   response=c.tool('resolve_experience',{'task_context':{}})
  finally:c.close()
 write(out/'BEFORE_TRANSPORT_CLEANUP.json',b.metadata)
 events=[json.loads(s) for s in (out/'before_mcp.jsonl').read_text().splitlines()]
 rejected=any(x.get('reason')=='MESSAGE_SIZE_LIMIT' for x in events)
 write(out/'BEFORE_FIX_REPRODUCTION.json',{'at':now(),'status':'EXPECTED_FAIL' if rejected else 'REPRO_NOT_OBSERVED','transport':'Official MCP SDK stdio via real scoped UDS broker','limit_bytes':MAX_MESSAGE_BYTES,'response':response,'message_size_limit_observed':rejected,'full_graph_nodes':before['node_count'],'full_graph_edges':before['edge_count'],'full_graph_sha256':before['graph_sha256'],'graph_copy':copyname,'no_edges_deleted':True,'model_requests':0});assert rejected
# Trusted-host capture of exact SDK stdout, outside the public bounded broker;
# this measures the rejected frame without changing the transport or SDK.
copy2='aevora_v5c1_prefx_stdio_'+uuid.uuid4().hex;repo._graph.copy(copy2);os.environ['AEVORA_FALKORDB_GRAPH']=copy2
p=subprocess.Popen([sys.executable,'-m','aevora.mcp_server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'official_stdio_stderr.log').open('xb'),bufsize=0)
def send(value):p.stdin.write(json.dumps(value,separators=(',',':')).encode()+b'\n');p.stdin.flush()
buffer=bytearray()
def frame():
 deadline=time.monotonic()+90
 while b'\n' not in buffer:
  if time.monotonic()>deadline:raise TimeoutError('bounded trusted SDK measurement')
  if not select.select([p.stdout],[],[],.2)[0]:continue
  chunk=os.read(p.stdout.fileno(),65536)
  if not chunk:raise RuntimeError('SDK closed during trusted measurement')
  buffer.extend(chunk)
  if len(buffer)>8*1024*1024:raise RuntimeError('trusted measurement 8 MiB safety bound')
 i=buffer.index(b'\n')+1;raw=bytes(buffer[:i]);del buffer[:i];return raw
try:
 send({'protocol':'aevora-mcp-uds-v1','run_id':'v5c1-byte-measure-'+uuid.uuid4().hex,'public_context':public_context('multi_process_shared_sqlite'),'connection_id':str(uuid.uuid4()),'enable_proposals':True})
 send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Aevora trusted byte measurement','version':'1'}}});initial=frame();(out/'official_stdio_initialize.json').write_bytes(initial)
 send({'jsonrpc':'2.0','method':'notifications/initialized'})
 send({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'resolve_experience','arguments':{'task_context':{}}}})
 raw=frame();(out/'official_resolve_wire.json').write_bytes(raw);result=json.loads(raw)['result'];structured=result['structuredContent']
 text=result['content'][0]['text'];assert json.loads(text)==structured
 counts=collections.Counter();pathcounts={}
 for candidate in structured['candidates']:
  bundle=candidate['evidence_bundle'];paths=bundle['paths'];pathcounts[candidate['experience_id']]={'paths':len(paths),'observed_outcome_paths':len(bundle['observed_outcome_paths']),'candidate_utf8_bytes':len(json.dumps(candidate,ensure_ascii=False).encode())}
 def visit(v):
  if isinstance(v,dict):
   if 'id' in v and isinstance(v['id'],str):counts[v['id']]+=1
   for x in v.values():visit(x)
  elif isinstance(v,list):
   for x in v:visit(x)
 visit(structured)
 write(out/'ACTUAL_WIRE_SIZE.json',{'at':now(),'wire_utf8_bytes_including_newline':len(raw),'wire_sha256':hashlib.sha256(raw).hexdigest(),'limit_bytes':MAX_MESSAGE_BYTES,'direction':'OFFICIAL_SDK_TO_PARTICIPANT','tool':'resolve_experience','structured_json_compact_utf8_bytes':len(json.dumps(structured,ensure_ascii=False,separators=(',',':')).encode()),'sdk_text_utf8_bytes':len(text.encode()),'text_and_structured_are_equal':True,'candidate_count':len(structured['candidates']),'path_counts':pathcounts,'repeated_record_ids':dict(counts.most_common(24)),'graph_restored_sha256':before['graph_sha256'],'probe_copy':copy2,'sdk':'mcp1.26.0; actual official newline UTF8 serialization','no_product_changes':True})
 print('G1_FULL_GRAPH_REPRODUCED',len(raw),'bytes',len(structured['candidates']),'candidates',flush=True)
finally:
 p.terminate();p.wait(timeout=5);repo.close()
