"""Runs with only public wheels/source, copied system tools and owned DB authority."""
import os,sys,json,uuid,secrets,tempfile,socket,threading,time,urllib.request,urllib.error,hashlib,sqlite3,importlib.metadata
from pathlib import Path
import aevora,aevora_observatory
from aevora.graph_repository import GraphRepository
from aevora.mcp_broker import MCPBroker,PROTOCOL,MAX_MESSAGE_BYTES
from aevora.historical_import import public_context
from aevora_observatory.server import create_app
import uvicorn
O=Path('/output');checks=[]
def check(label,ok,observed):
 checks.append({'name':label,'status':'PASS' if ok else 'FAIL','observed':observed});assert ok,label
def write(name,value):
 with (O/name).open('x') as f:json.dump(value,f,indent=2)
try:
 import benchmark
 raise AssertionError('maintainer Benchmark importable from clean product namespace')
except ModuleNotFoundError:check('maintainer_absent',True,'benchmark not installed or mounted')
import importlib.util
check('host_facade_absent',importlib.util.find_spec('aevora_maintainer') is None,'private Host facade not installed or mounted')
check('public_wheel_imports', '/clean-venv-final2/' in aevora.__file__ and '/clean-venv-final2/' in aevora_observatory.__file__,{'core':aevora.__file__,'console':aevora_observatory.__file__})
from aevora.contracts import TenantBinding, TrustRegistry, PROFILE, schema
check('v2_schema_packaged',schema('resolve_experience.arguments')['required']==['task_context'],PROFILE)
check('host_identity_absent',not Path('/home/PRIVATE_MAINTAINER/.codex/auth.json').exists() and not Path('/workspace/evaluator').exists(),'No host identity or evaluator mount')
main=GraphRepository.from_environment();before=main.state_fingerprint();name='aevora_g23_final_public_'+uuid.uuid4().hex;main._graph.copy(name);os.environ['AEVORA_FALKORDB_GRAPH']=name;r=GraphRepository.from_environment()
try:
 with tempfile.TemporaryDirectory(prefix='g23-public-') as td:
  token=secrets.token_hex(32);b=MCPBroker(run_id='g23-public-'+uuid.uuid4().hex,public_context=public_context('multi_process_shared_sqlite'),socket_path=Path(td)/'mcp.sock',run_token=token,event_path=O/'public_mcp.jsonl',enable_proposals=True)
  with b:
   sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(30);sock.connect(str(b.socket_path));reader=sock.makefile('rb');sock.sendall(json.dumps({'protocol':PROTOCOL,'run_id':b.run_id,'token':token,'nonce':secrets.token_hex(32)}).encode()+b'\n');assert json.loads(reader.readline())['aevora_transport']=='READY'
   def rpc(i,method,params):
    request={'jsonrpc':'2.0','id':i,'method':method,'params':params};sock.sendall(json.dumps(request).encode()+b'\n');raw=reader.readline(MAX_MESSAGE_BYTES+1);assert raw and len(raw)<=MAX_MESSAGE_BYTES
    with (O/'public_client.jsonl').open('a') as f:f.write(json.dumps({'request':request,'response':json.loads(raw),'wire_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})+'\n')
    return json.loads(raw)['result']
   try:
    rpc(1,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Aevora clean wheel smoke','version':'1'}});sock.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    catalog=rpc(2,'tools/list',{});check('clean_official_four_tools',len(catalog['tools'])==4,[v['name'] for v in catalog['tools']])
    q=rpc(3,'tools/call',{'name':'resolve_experience','arguments':{'task_context':{}}});check('clean_real_full_graph_query',not q.get('isError') and len(q['structuredContent']['candidates'])==2,q['structuredContent'])
    c=q['structuredContent']['candidates'][0]
    bundle=rpc(4,'tools/call',{'name':'build_evidence_bundle','arguments':{'experience_id':c['experience_id'],'query_id':q['structuredContent']['query_id']}});check('clean_full_evidence',not bundle.get('isError'),bundle['structuredContent'].get('experience_id'))
   finally:reader.close();sock.close()
  check('clean_mcp_cleanup',b.metadata['handler_cleanup_complete'] and b.metadata['token_revoked'],b.metadata)
 # Explicit v2 empty graph in the clean public package; no synthetic successful strategy.
 from aevora.contracts import record, canonical_json
 from aevora.mcp_v2 import ReadGrant
 from datetime import datetime,timezone,timedelta
 legacy_graph=os.environ['AEVORA_FALKORDB_GRAPH']
 empty_name='aevora_v2_clean_'+uuid.uuid4().hex
 os.environ['AEVORA_FALKORDB_GRAPH']=empty_name
 empty_transport=GraphRepository.from_environment()
 empty=empty_transport.v2(TenantBinding('public-clean-tenant',empty_name),TrustRegistry());empty.initialize()
 grant=ReadGrant('public-clean-tenant','public-clean-run','public-clean-session','one',(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
 empty.put_node(record(empty.tenant,'Session',[grant.run_id,grant.session_id,grant.generation],run_id=grant.run_id,session_id=grant.session_id,grant_generation=grant.generation,profile=PROFILE,state='ACTIVE',valid_until=grant.valid_until))
 conf=O/'v2-config.json';conf.write_text(canonical_json(dict(binding=empty.binding.__dict__,registry=empty.registry.__dict__,facts={},grant=grant.__dict__)));conf.chmod(0o600)
 with tempfile.TemporaryDirectory(prefix='g21-public-v2-') as td:
  token=secrets.token_hex(32);b=MCPBroker(run_id=grant.run_id,public_context={},socket_path=Path(td)/'mcp.sock',run_token=token,event_path=O/'v2_mcp.jsonl',enable_proposals=True,protocol_profile=PROFILE,v2_config_path=str(conf))
  with b:
   sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(30);sock.connect(str(b.socket_path));reader=sock.makefile('rb')
   sock.sendall(json.dumps(dict(protocol=PROTOCOL,run_id=b.run_id,token=token,nonce=secrets.token_hex(32))).encode()+b'\n');assert json.loads(reader.readline())['aevora_transport']=='READY'
   try:
    rpc(1,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Aevora public v2 smoke','version':'1'}});sock.sendall(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    q=rpc(2,'tools/call',{'name':'resolve_experience','arguments':{'task_context':{}}})
    check('clean_actual_v2_empty_sdk',not q.get('isError') and q['structuredContent']['status']=='EMPTY' and q['structuredContent']['read_scope']['protocol_profile']==PROFILE,q)
   finally:reader.close();sock.close()
 empty_transport.close();os.environ['AEVORA_FALKORDB_GRAPH']=legacy_graph
 app=create_app(replay_root=Path('/product/h4'),replay_sha256=hashlib.sha256(Path('/product/h4/hero_scenario_contract.json').read_bytes()).hexdigest())
 listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(app,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]});thread.start()
 try:
  end=time.monotonic()+10
  while not server.started:
   assert time.monotonic()<end;time.sleep(.05)
  graphbefore=r.state_fingerprint()
  url='http://127.0.0.1:'+str(port)
  with urllib.request.urlopen(url+'/api/health?mode=LIVE&case=case-c&context=workers') as response:
   data=json.load(response);check('actual_console_live_http',response.status==200 and data['mode']=='LIVE' and data['status']=='AVAILABLE',data);write('console_live_health.json',data)
  for label,path,method,expected in [('readonly','/api/health?mode=LIVE','POST',403),('no_private_resource','/api/private?mode=LIVE','GET',403),('invalid_no_fallback','/api/health?mode=FAKE','GET',400)]:
   try:urllib.request.urlopen(urllib.request.Request(url+path,method=method));raise AssertionError(label)
   except urllib.error.HTTPError as error:check(label,error.code==expected,json.load(error))
  check('console_read_has_no_graph_writes',r.state_fingerprint()==graphbefore,r.state_fingerprint())
 finally:server.should_exit=True;thread.join(timeout=10);listener.close();check('console_server_cleanup',not thread.is_alive(),'thread stopped')
 check('original_full_graph_unchanged',main.state_fingerprint()==before,main.state_fingerprint())
 write('RESULT.json',{'status':'PASS','checks':checks,'python':sys.version,'sqlite':sqlite3.sqlite_version,'packages':{n:importlib.metadata.version(n) for n in ['aevora-core','aevora-console','mcp','pydantic','falkordb']},'model_requests':0,'scope':'CLEAN_PUBLIC_WHEELS_REAL_SDK_REAL_DB_REAL_HTTP; no maintainer package or Oracle mounted'})
 print('CLEAN_PUBLIC_CORE_MCP_CONSOLE_PASS',len(checks),flush=True)
finally:r.close();main.close()
