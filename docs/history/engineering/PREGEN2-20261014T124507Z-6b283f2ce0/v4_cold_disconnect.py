from runtime import *
import subprocess,time,urllib.request,urllib.error,uuid,socket
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());cold=json.loads((E/'04_falkordb/recovery-attempt2/RESULT.json').read_text());out=E/'05_product/cold_db_disconnect';out.mkdir(mode=0o700)
name='aevora-pregen2-cold-view-'+uuid.uuid4().hex[:8];port=17866
with socket.socket() as s:s.bind(('127.0.0.1',port))
assert record('v4-cold-db-start-for-http',['docker','start',cold['cold_container']])==0
args=['docker','run','--rm','--name',name,'--network','host','--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--cpus','1','--memory','256m','--mount','type=bind,src='+cfg['password_file']+',dst=/run/secrets/db,readonly','--env','AEVORA_FALKORDB_PASSWORD_FILE=/run/secrets/db','--env','AEVORA_FALKORDB_PORT=17706','--env','AEVORA_FALKORDB_GRAPH='+cfg['graph'],'aevora-pregen2-local:6b283f2ce0-staged2','--replay-root','/opt/aevora/h4','--replay-sha256',sha(P/'h4/hero_scenario_contract.json'),'--port',str(port)]
stdout=(out/'viewer-stdout.log').open('xb');stderr=(out/'viewer-stderr.log').open('xb');start=now();p=subprocess.Popen(args,stdout=stdout,stderr=stderr)
def http(mode,label):
 t=time.monotonic()
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/overview?case=case-b&mode='+mode,timeout=60) as r:status=r.status;b=r.read()
 except urllib.error.HTTPError as e:status=e.code;b=e.read()
 (out/(label+'.json')).write_bytes(b);v=json.loads(b);write(out/(label+'-receipt.json'),{'http_status':status,'elapsed_seconds':time.monotonic()-t,'sha256':sha(out/(label+'.json')),'at':now()});return status,v
try:
 deadline=time.monotonic()+30
 while True:
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as r:
    if r.status==200:break
  except OSError:
   if p.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Viewer failed startup')
   time.sleep(.05)
 status,before=http('LIVE','BEFORE');assert status==200 and before['mode']=='LIVE'
 assert record('v4-cold-db-normal-stop-for-outage',['docker','stop','--time','15',cold['cold_container']])==0
 status,down=http('LIVE','UNAVAILABLE');assert status==503 and down['fallback'] is False
 status,replay=http('REPLAY','EXPLICIT_REPLAY');assert status==200 and replay['mode']=='REPLAY'
 assert record('v4-cold-db-normal-restart-for-http',['docker','start',cold['cold_container']])==0
 status,after=http('LIVE','AFTER');assert status==200 and after['mode']=='LIVE' and before['graph']==after['graph'] and before['decisions']==after['decisions']
 write(out/'RESULT.json',{'status':'PASS','before_http':200,'down_live_http':503,'explicit_replay_http':200,'after_live_http':200,'real_graph_unchanged_after_stop_start':True,'model_calls':0,'owned_cold_container':cold['cold_container'],'at':now()})
finally:
 stopped=subprocess.run(['docker','stop','--time','10',name],capture_output=True);code=p.wait(30);stdout.close();stderr.close();write(out/'VIEWER_COMMAND.json',{'argv':args,'started_at':start,'ended_at':now(),'exit_code':code,'stop_exit':stopped.returncode,'stdout_sha256':sha(out/'viewer-stdout.log'),'stderr_sha256':sha(out/'viewer-stderr.log')})
 record('v4-cold-db-stop-after-http',['docker','stop','--time','15',cold['cold_container']])
print('V4 actual DB disconnect503/replay200/recovery200 PASS')
