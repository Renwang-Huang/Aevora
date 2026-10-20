from pathlib import Path
import sys,os,json,uuid,tempfile,secrets,socket,http.client
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from integrations.codex_agent import CodexConfig,CodexAgentAdapter
from integrations.agents import TaskInput,ExecutionContext
from integrations.gateway_broker import SecureModelBroker
from integrations.providers import ProviderConfig
out=E/'03_benchmark/negative_transport_trials/actual';out.mkdir(mode=0o700)
r=BenchmarkRunner(out/'startup-runs');p=r.prepare('A');run=out/'startup-runs'/p['run_id'];w=build_participant(run/'workspace',run/'participant',agent_mode='single')
config=CodexConfig(binary=E/'owned_runtime/native/absent-codex',auth_path=Path('/maintainer/gateway.key'),provider_id='gateway',completion_policy='completion-aware',timeout_seconds=None,request_budget=1,agent_mode='single',reasoning_effort='max',model='gpt-5.6-terra')
result=CodexAgentAdapter(config).execute(TaskInput('A','1.0.0','Actual missing-executable startup negative; no model request'),ExecutionContext(run.name,str(w),constraints={'archive':str(run),'baseline':str(run/'workspace')}))
assert result.runtime_metadata['failure_kind']=='STARTUP_FAILED' and result.submission is None
write(out/'MISSING_EXECUTABLE_RESULT.json',{'run_id':run.name,'execution_status':result.status.value,'runtime':result.runtime_metadata,'model_calls':0,'actual_missing_path':True})
with tempfile.TemporaryDirectory(prefix='pregen2-neg-') as d:
 token=secrets.token_urlsafe(32)
 with SecureModelBroker(ProviderConfig(base_url='https://api.renwang-huang.top/v1'),Path('/maintainer/gateway.key'),run_id='pregen2-negative-'+uuid.uuid4().hex,socket_path=Path(d)/'broker.sock',run_token=token,request_budget=1,max_concurrency=1,completion_policy='completion-aware',request_timeout=None,token_ttl_seconds=None,event_path=out/'oversized_transport.jsonl') as b:
  class Conn(http.client.HTTPConnection):
   def connect(self):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(10);self.sock.connect(str(b.socket_path))
  c=Conn('localhost');c.putrequest('POST','/v1/responses');c.putheader('Authorization','Bearer '+token);c.putheader('Content-Type','application/json');c.putheader('Content-Length',str(b.max_body_bytes+1));c.endheaders()
  send_error=None
  try:c.send(b'x'*(b.max_body_bytes+1))
  except (BrokenPipeError,ConnectionResetError,OSError) as e:send_error=type(e).__name__
  status=None;read_error=None
  try:res=c.getresponse();status=res.status;res.read()
  except (OSError,http.client.HTTPException) as e:read_error=type(e).__name__
  finally:c.close()
 metadata=b.metadata
 assert metadata['upstream_requests']==0
 assert any(x.get('error_category')=='REQUEST_TOO_LARGE' or x.get('category')=='REQUEST_TOO_LARGE' for x in metadata['request_records']), metadata
 write(out/'OVERSIZED_ACTUAL_RESULT.json',{'status':'PASS_REJECTED_WITHOUT_UPSTREAM','http_status':status,'client_send_error':send_error,'client_read_error':read_error,'metadata':metadata,'at':now(),'classification':'REAL_SCOPED_UNIX_HTTP_OVERSIZED_SEND_CLOSE; NO_PROVIDER_REQUEST_OR_MOCK'})
print('V2 actual startup/oversized negatives complete')
