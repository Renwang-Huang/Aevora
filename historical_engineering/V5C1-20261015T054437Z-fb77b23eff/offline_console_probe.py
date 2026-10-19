"""Actual LIVE HTTP while owned DB is stopped; Replay must not replace it."""
from pathlib import Path
import sys,json,socket,threading,time,urllib.request,urllib.error,hashlib
E=Path(__file__).resolve().parent;sys.path.insert(0,str(E))
from audit import write,now
from aevora_observatory.server import create_app
import uvicorn
app=create_app(replay_root=E/'owned_runtime/source/h4',replay_sha256=hashlib.sha256((E/'owned_runtime/source/h4/hero_scenario_contract.json').read_bytes()).hexdigest());listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
server=uvicorn.Server(uvicorn.Config(app,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]});thread.start()
try:
 end=time.monotonic()+10
 while not server.started:
  assert time.monotonic()<end;time.sleep(.05)
 try:urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/health?mode=LIVE&case=case-c&context=workers',timeout=15);raise AssertionError('LIVE outage silently succeeded')
 except urllib.error.HTTPError as error:
  body=json.load(error);ok=error.code==503 and body['mode']=='LIVE' and body['fallback'] is False
  write(E/'05_graph/db_outage/OFFLINE_CONSOLE_RESULT.json',{'status':'PASS' if ok else 'FAIL','at':now(),'http_status':error.code,'response':body,'model_requests':0,'actor':'TRUSTED_HOST_ACTUAL_STOPPED_DB_LIVE_HTTP_CONTROL'});assert ok
finally:server.should_exit=True;thread.join(timeout=10);listener.close();assert not thread.is_alive()
print('ACTUAL_CONSOLE_LIVE_DB_OUTAGE_FAILS_CLOSED')
