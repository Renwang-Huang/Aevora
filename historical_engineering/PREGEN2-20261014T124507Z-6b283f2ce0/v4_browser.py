from runtime import *
import signal,socket,urllib.request,urllib.error,uuid,time,subprocess
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());out=E/'05_product/public_browser';out.mkdir(mode=0o700)
source=E/'05_product/public-build-1/source';image='aevora-pregen2-local:'+C['run_id'].split('-')[-1]
assert record('v4-public-image-build',['docker','build','-f',str(source/'h4/deploy/Dockerfile'),'-t',image,str(source)])==0
assert record('v4-public-image-save',['docker','save','-o',str(E/'05_product/public_image.tar'),image])==0
pin=sha(P/'h4/hero_scenario_contract.json');empty='aevora_pregen2_empty_'+uuid.uuid4().hex
base=['docker','run','--rm','--network','host','--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--cpus','1','--memory','256m','--mount','type=bind,src='+cfg['password_file']+',dst=/run/secrets/db,readonly','--env','AEVORA_FALKORDB_PASSWORD_FILE=/run/secrets/db','--env','AEVORA_FALKORDB_PORT='+str(cfg['port'])]
assert record('v4-image-empty-init',[*base,'--env','AEVORA_FALKORDB_GRAPH='+empty,'--entrypoint','python',image,'-I','-m','aevora','init'])==0
procs=[]
def launch(label,port,graph,dbport=None):
 with socket.socket() as s:s.bind(('127.0.0.1',port))
 name='aevora-pregen2-view-'+label+'-'+uuid.uuid4().hex[:8];args=list(base)
 if dbport is not None:args+=['--env','AEVORA_FALKORDB_PORT='+str(dbport)]
 argv=[*args,'--name',name,'--env','AEVORA_FALKORDB_GRAPH='+graph,image,'--replay-root','/opt/aevora/h4','--replay-sha256',pin,'--port',str(port)]
 stdout=(out/(label+'-stdout.log')).open('xb');stderr=(out/(label+'-stderr.log')).open('xb');begin=now();p=subprocess.Popen(argv,stdout=stdout,stderr=stderr);procs.append((label,name,p,argv,stdout,stderr,begin))
 deadline=time.monotonic()+30
 while True:
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/',timeout=1) as r:
    if r.status==200:return
  except OSError:
   if p.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Actual public server failed to start')
   time.sleep(.05)
def http(url,name):
 try:
  with urllib.request.urlopen(url,timeout=10) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 (out/(name+'.json')).write_bytes(body);return status,json.loads(body)
try:
 launch('main',17860,cfg['graph']);launch('empty',17861,empty)
 controls=json.loads((E/'04_falkordb/graph_controls-attempt3/RESULT.json').read_text())['graph'];launch('controls',17862,controls)
 browser=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch/aevora_gen1_5_2_evidence/Gen1.5.2-20261014T065322Z-01fb65a2-eac4-4ce4-a468-9fe5de1a8567-prearchive-review/browser_runtime')
 assert record('v4-actual-chromium-17',['node',str(P/'console/browser/validate.mjs')],cwd=P,env={'PLAYWRIGHT_BROWSERS_PATH':str(browser),'AEVORA_BROWSER_OUTPUT':str(out/'browser'),'AEVORA_BROWSER_URL':'http://127.0.0.1:17860','AEVORA_EMPTY_BROWSER_URL':'http://127.0.0.1:17861'})==0
 status,v=http('http://127.0.0.1:17862/api/overview?case=case-c&mode=LIVE&context=workers','LIVE_ACTUAL_CONFLICT_WITHDRAWAL');assert status==200 and v['mode']=='LIVE' and any(d['decision']=='VERIFY' for d in v['decisions']) and any(h.get('state')=='WITHDRAWN' for h in v['candidate_heads'])
 # Installation and browser reads can coexist; DB fault injection must wait
 # for the other actual SDK consumer to close its owner channel.
 installer=E/'commands/v4-clean-public-only-install-retry1/receipt.json';deadline=time.monotonic()+600
 while not installer.exists():
  if time.monotonic()>deadline:raise RuntimeError('INSTALL_PENDING; DB pause withheld')
  time.sleep(.25)
 assert json.loads(installer.read_text())['exit_code']==0
 # Actual owned database outage while the same public server remains alive.
 assert record('v4-owned-db-disconnect',['docker','pause',cfg['container']])==0
 status,v=http('http://127.0.0.1:17860/api/overview?case=case-b&mode=LIVE','LIVE_DB_STOPPED');assert status==503 and v['fallback'] is False
 status,v=http('http://127.0.0.1:17860/api/overview?case=case-b&mode=REPLAY','EXPLICIT_REPLAY_DB_STOPPED');assert status==200 and v['mode']=='REPLAY'
 assert record('v4-owned-db-resume',['docker','unpause',cfg['container']])==0
 status,v=http('http://127.0.0.1:17860/api/overview?case=case-b&mode=LIVE&context=threads','LIVE_RECONNECTED');assert status==200 and v['mode']=='LIVE' and any(d['decision']=='APPLY' for d in v['decisions'])
finally:
 # Resume only this audit's DB if an HTTP assertion fails while paused.
 paused=subprocess.run(['docker','inspect','--format','{{.State.Paused}}',cfg['container']],capture_output=True,text=True)
 if paused.returncode==0 and paused.stdout.strip()=='true':record('v4-owned-db-emergency-resume',['docker','unpause',cfg['container']])
 for label,name,p,argv,stdout,stderr,begin in procs:
  stopped=subprocess.run(['docker','stop','--time','10',name],capture_output=True);code=p.wait(30);stdout.close();stderr.close();write(out/(label+'-command.json'),{'argv':argv,'exit_code':code,'started_at':begin,'ended_at':now(),'owner_stop_exit':stopped.returncode,'stdout_sha256':sha(out/(label+'-stdout.log')),'stderr_sha256':sha(out/(label+'-stderr.log'))})
  assert stopped.returncode==code==0
v=json.loads((out/'browser/RESULT.json').read_text());assert v['status']=='PASS'
write(out/'RESULT.json',{'status':'PASS','actual_browser_checks':len(v['checks']),'http_count':len(v['http']),'browser_source':'ACTUAL_CHROMIUM_NO_MOCKED_ROUTES','current_db_live':True,'historical_replay_explicit':True,'owned_actual_db_outage_503':True,'owned_db_recovery_live_200':True,'actual_conflict_withdrawal_http':True,'model_calls':0,'at':now()})
print('V4 browser PASS',len(v['checks']))
