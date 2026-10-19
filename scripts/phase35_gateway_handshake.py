"""Trusted, bounded live API handshake; archives metadata only, never credentials."""
import datetime,hashlib,json,os,pathlib,secrets,socket,ssl,sys,tempfile,time
from uuid import uuid4
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from integrations.providers import ProviderConfig
from integrations.gateway_broker import SecureModelBroker
from integrations.participant_bridge import UnixConnection
archive=pathlib.Path(sys.argv[1]).resolve()/'gateway_handshake';archive.mkdir()
record={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'third_party_endpoint':'api.renwang-huang.top','privacy_scope':'Only public synthetic handshake prompts; TLS verified; no private benchmark inputs','requested_model':'gpt-5.6-terra','requested_effort':'max','attempts':[]}
context=ssl.create_default_context()
record['dns_addresses']=sorted({row[4][0] for row in socket.getaddrinfo('api.renwang-huang.top',443,type=socket.SOCK_STREAM)})
with socket.create_connection(('api.renwang-huang.top',443),timeout=15) as connection:
 with context.wrap_socket(connection,server_hostname='api.renwang-huang.top') as tls:
  record['tls']={'verified':True,'version':tls.version(),'certificate_sha256':hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()}
selected=None
for base in ('https://api.renwang-huang.top','https://api.renwang-huang.top/v1'):
 with tempfile.TemporaryDirectory(prefix='of-hs-') as td:
  token=secrets.token_urlsafe(32)
  with SecureModelBroker(ProviderConfig(base_url=base),pathlib.Path(os.environ['ORDERFLOW_GATEWAY_SECRET_PATH']),run_id=str(uuid4()),socket_path=pathlib.Path(td)/'b.sock',run_token=token,request_budget=8,max_concurrency=1) as broker:
   client=UnixConnection(str(broker.socket_path));client.request('GET','/v1/models',headers={'Authorization':'Bearer '+token}); response=client.getresponse();body=response.read();client.close()
   try: value=json.loads(body)
   except ValueError:value={}
   ids=[item.get('id') for item in value.get('data',[]) if isinstance(item,dict)] if isinstance(value,dict) else []
   record['attempts'].append({'api_root':base,'http_status':response.status,'json_type':type(value).__name__,'models_count':len(ids),'target_model_listed':'gpt-5.6-terra' in ids,'broker':broker.metadata})
   if response.status==200 and 'gpt-5.6-terra' in ids: selected=base;break
(archive/'api_root_discovery.json').write_text(json.dumps(record,indent=2)+'\n')
if selected is None: raise RuntimeError('Gateway model discovery failed; no endpoint/model substitution')
with tempfile.TemporaryDirectory(prefix='of-hs-') as td:
 token=secrets.token_urlsafe(32)
 with SecureModelBroker(ProviderConfig(base_url=selected),pathlib.Path(os.environ['ORDERFLOW_GATEWAY_SECRET_PATH']),run_id=str(uuid4()),socket_path=pathlib.Path(td)/'b.sock',run_token=token,request_budget=8,max_concurrency=1) as broker:
  def request(label,body):
   client=UnixConnection(str(broker.socket_path));data=json.dumps(body).encode();started=time.monotonic();client.request('POST','/v1/responses',body=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'});response=client.getresponse(); raw=response.read();client.close()
   if body.get('stream'):
    events=[json.loads(line[6:]) for line in raw.decode().splitlines() if line.startswith('data: ') and line[6:]!='[DONE]']; completed=[event['response'] for event in events if event.get('type')=='response.completed'];value=completed[-1] if completed else {};extra={'sse_event_count':len(events),'terminal_completed':bool(completed)}
   else:
    value=json.loads(raw);extra={}
   safe={'label':label,'http_status':response.status,'elapsed_seconds':time.monotonic()-started,'body_sha256':hashlib.sha256(raw).hexdigest(),'actual_model':value.get('model'),'actual_effort':value.get('reasoning',{}).get('effort'),'status':value.get('status'),'response_id':value.get('id'),'usage':value.get('usage'),'output_types':[item.get('type') for item in value.get('output',[])],**extra}
   (archive/(label+'.json')).write_text(json.dumps(safe,indent=2)+'\n')
   assert response.status==200 and value.get('status')=='completed',safe
   assert value.get('model')=='gpt-5.6-terra' and value.get('reasoning',{}).get('effort')=='max',safe
   return value
  common={'model':'gpt-5.6-terra','reasoning':{'effort':'max'},'max_output_tokens':1024,'store':False}
  request('text',{**common,'input':'Reply with exactly OK.'})
  request('sse',{**common,'input':'Reply with exactly STREAM_OK.','stream':True})
  tools=[{'type':'function','name':'public_echo','description':'Return public echo text.','parameters':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False},'strict':True}]
  initial=[{'role':'user','content':'Call public_echo with text HELLO once, then acknowledge the result.'}]
  first=request('tool_call',{**common,'input':initial,'tools':tools,'tool_choice':{'type':'function','name':'public_echo'}})
  calls=[item for item in first['output'] if item.get('type')=='function_call'];assert len(calls)==1
  request('tool_return',{**common,'input':initial+first['output']+[{'type':'function_call_output','call_id':calls[0]['call_id'],'output':'HELLO'}],'tools':tools,'tool_choice':'none'})
  record['responses_transport']=broker.metadata
record['selected_api_root']=selected;record['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();record['result']='PASS';(archive/'summary.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'result':'PASS','api_root':selected,'model':'gpt-5.6-terra','effort':'max','real_responses_requests':4}))
