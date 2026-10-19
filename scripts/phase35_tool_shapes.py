"""A real isolated Codex CLI with a synthetic local upstream 429; zero live API calls."""
import json,os,pathlib,sys,tempfile,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmark.runner import BenchmarkRunner
import integrations.codex_agent as runtime
from integrations.codex_agent import CodexConfig
from integrations.gateway_broker import SecureModelBroker
archive=pathlib.Path(sys.argv[1]).resolve();archive.mkdir()
class Reject(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):self.reject()
 def do_POST(self):
  payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
  schemas=[]
  def collect(value,prefix=''):
   if isinstance(value,dict):
    if 'name' in value or 'type' in value:
     schemas.append({key:value[key] for key in ('name','type','defer_loading') if key in value})
    for key in ('tools','functions'):
     if key in value:collect(value[key])
   elif isinstance(value,list):
    for item in value:collect(item)
  collect(payload.get('tools',[]))
  (archive/'native_api_tool_shapes.json').write_text(json.dumps({'source':'actual installed CLI POST; only tool names/types; request body not archived','schemas':schemas,'model':payload.get('model'),'reasoning':payload.get('reasoning')},indent=2)+'\n')
  self.reject()
 def reject(self):
  body=b'{"error":{"type":"synthetic_rate_limit","message":"controlled local 429"}}'
  self.send_response(429);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Reject);server.daemon_threads=True
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with tempfile.TemporaryDirectory(prefix='of-fault-') as td:
  secret=pathlib.Path(td)/'synthetic.key';secret.write_text('synthetic-local-fault-key-not-a-live-credential');secret.chmod(0o600)
  def factory(provider,path,**kwargs):return SecureModelBroker(provider,path,test_upstream_base_url=f'http://127.0.0.1:{server.server_port}/v1',**kwargs)
  runtime.SecureModelBroker=factory
  config=CodexConfig(pathlib.Path(os.environ['ORDERFLOW_CODEX_BINARY']),secret,model='gpt-5.6-terra',provider_id='gateway',reasoning_effort='max',timeout_seconds=30,request_budget=8)
  result=BenchmarkRunner(archive/'fault-runs').run_agent('A',config=config)
  metadata=json.loads((archive/'fault-runs'/result['run_id']/'runtime_metadata.json').read_text())
  summary={'source':'real installed CLI; synthetic controlled local 429; not a live model challenge','real_gateway_requests':0,'run_id':result['run_id'],'runtime_status':result['runtime_status'],'evaluation_status':result['evaluation_status'],'integration_status':result['integration_status'],'failure_kind':metadata['failure_kind'],'transport_errors':metadata.get('model_broker',{}).get('error_counts'),'cgroup_cleanup':metadata.get('resource_cgroup',{}).get('cleanup_complete'),'state_cleanup':result.get('agent_state_cleanup')}
  (archive/'fault_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
  assert result['runtime_status']=='ERROR' and result['evaluation_status']=='NOT_RUN' and result['overall_status']=='ERROR'
  assert metadata['model_broker']['error_counts'].get('UPSTREAM_RATE_LIMITED',0)>0
  assert summary['cgroup_cleanup'] is True and summary['state_cleanup']=='PASS'
finally:server.shutdown();server.server_close();thread.join(timeout=2)
