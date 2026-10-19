"""Public native-namespace SSE tool compatibility probe, with no private input."""
import pathlib,os,json,sys,tempfile,secrets,hashlib
from uuid import uuid4
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from integrations.providers import ProviderConfig
from integrations.gateway_broker import SecureModelBroker
from integrations.participant_bridge import UnixConnection
out=pathlib.Path(sys.argv[1]).resolve()/'sse_tool_probe';out.mkdir()
with tempfile.TemporaryDirectory(prefix='of-st-') as td:
 token=secrets.token_urlsafe(32)
 with SecureModelBroker(ProviderConfig(base_url='https://api.renwang-huang.top/v1'),pathlib.Path(os.environ['ORDERFLOW_GATEWAY_SECRET_PATH']),run_id=str(uuid4()),socket_path=pathlib.Path(td)/'b.sock',run_token=token,request_budget=2,max_concurrency=1) as broker:
  tool={'type':'function','name':'public_echo','description':'Echo one public string','parameters':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False},'strict':True}
  body={'model':'gpt-5.6-terra','reasoning':{'effort':'max'},'input':'Call public_echo with text HELLO exactly once.','tools':[{'type':'namespace','name':'public_tools','description':'Public tools','tools':[tool]}],'tool_choice':'required','stream':True,'store':False,'max_output_tokens':1024}
  client=UnixConnection(str(broker.socket_path));client.request('POST','/v1/responses',body=json.dumps(body),headers={'Content-Type':'application/json','Authorization':'Bearer '+token});response=client.getresponse();raw=response.read();client.close()
  (out/'public_sse.log').write_bytes(raw)
  events=[json.loads(line[6:]) for line in raw.decode().splitlines() if line.startswith('data: ') and line[6:]!='[DONE]']
  completed=[e['response'] for e in events if e.get('type')=='response.completed'];calls=[item for item in completed[-1].get('output',[]) if item.get('type')=='function_call'] if completed else []
  summary={'http_status':response.status,'event_types':[e.get('type') for e in events],'arguments_delta':[e.get('delta') for e in events if e.get('type')=='response.function_call_arguments.delta'],'calls':calls,'model':completed[-1].get('model') if completed else None,'effort':completed[-1].get('reasoning',{}).get('effort') if completed else None,'broker':broker.metadata,'sha256':hashlib.sha256(raw).hexdigest()}
  (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='broker'}))
  assert response.status==200 and len(calls)==1 and json.loads(calls[0]['arguments'])=={'text':'HELLO'}
  assert ''.join(summary['arguments_delta'])==calls[0]['arguments']
