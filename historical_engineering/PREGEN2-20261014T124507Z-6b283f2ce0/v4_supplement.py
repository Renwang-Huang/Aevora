from runtime import *
import subprocess,time,socket,uuid,urllib.request
out=E/'05_product/browser_supplement';out.mkdir(mode=0o700);cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());controls=json.loads((E/'04_falkordb/graph_controls-attempt3/RESULT.json').read_text())['graph'];procs=[]
def launch(label,port,graph):
 with socket.socket() as s:s.bind(('127.0.0.1',port))
 name='aevora-pregen2-extra-'+label+'-'+uuid.uuid4().hex[:8]
 argv=['docker','run','--rm','--name',name,'--network','host','--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--cpus','1','--memory','256m','--mount','type=bind,src='+cfg['password_file']+',dst=/run/secrets/db,readonly','--env','AEVORA_FALKORDB_PASSWORD_FILE=/run/secrets/db','--env','AEVORA_FALKORDB_PORT=17705','--env','AEVORA_FALKORDB_GRAPH='+graph,'aevora-pregen2-local:6b283f2ce0-staged2','--replay-root','/opt/aevora/h4','--replay-sha256',sha(P/'h4/hero_scenario_contract.json'),'--port',str(port)]
 stdout=(out/(label+'-stdout.log')).open('xb');stderr=(out/(label+'-stderr.log')).open('xb');begin=now();p=subprocess.Popen(argv,stdout=stdout,stderr=stderr);procs.append((name,p,stdout,stderr,argv,begin,label))
 deadline=time.monotonic()+30
 while True:
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/',timeout=1) as r:
    if r.status==200:return
  except OSError:
   if p.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Viewer startup failed')
   time.sleep(.05)
js="""import {createRequire} from 'node:module';import fs from 'node:fs/promises';import {spawnSync} from 'node:child_process';
const require=createRequire(PACKAGE);const {chromium,expect}=require('@playwright/test');const out=OUTPUT;const checks=[];let browser;
function edge(op,label){const r=spawnSync('python3',[DRIVER,label,'--',EDGE,op],{env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},encoding:'utf8'});if(r.status!==0)throw Error('Host edge command failed '+r.stderr);}
try{browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1280,height:900}});
await page.goto('http://127.0.0.1:17864/?page=explorer&case=case-c&mode=LIVE');await expect(page.getByRole('heading',{name:'VERIFY',exact:true}).first()).toBeVisible();await page.screenshot({path:out+'/conflict.png',fullPage:true});checks.push({name:'actual_live_conflict_why',status:'PASS'});
await page.getByRole('button',{name:'03 Governance Timeline',exact:true}).click();await expect(page.locator('.timeline-event').filter({hasText:'WITHDRAWN'}).first()).toBeVisible();await page.screenshot({path:out+'/withdrawn.png',fullPage:true});checks.push({name:'actual_live_withdrawal_timeline',status:'PASS'});
const denied=await page.request.post('http://127.0.0.1:17864/api/overview?mode=LIVE');expect(denied.status()).toBe(403);checks.push({name:'actual_browser_readonly_write_denial',status:'PASS'});
await page.goto('http://127.0.0.1:17865/?page=explorer&case=case-c&mode=LIVE&context=workers');await expect(page.getByRole('heading',{name:'APPLY',exact:true}).first()).toBeVisible();edge('cut','v4-browser-real-edge-cut');await page.getByRole('button',{name:'Refresh',exact:true}).click();await expect(page.getByRole('heading',{name:'VERIFY',exact:true}).first()).toBeVisible();await page.screenshot({path:out+'/real-edge-cut.png',fullPage:true});edge('restore','v4-browser-real-edge-restore');await page.getByRole('button',{name:'Refresh',exact:true}).click();await expect(page.getByRole('heading',{name:'APPLY',exact:true}).first()).toBeVisible();await page.screenshot({path:out+'/real-edge-restored.png',fullPage:true});checks.push({name:'real_host_edge_cut_browser_refresh_restore',status:'PASS'});
await fs.writeFile(out+'/RESULT.json',JSON.stringify({status:'PASS',checks,source:'Actual Chromium, actual Host graph operations, no route mocking'},null,2)+'\\n');
}finally{if(browser)await browser.close();}
"""
for a,b in [('PACKAGE',json.dumps(str(P/'console/package.json'))),('OUTPUT',json.dumps(str(out))),('DRIVER',json.dumps(str(E/'runtime.py'))),('EDGE',json.dumps(str(E/'v4_live_edge.py')))]:js=js.replace(a,b)
(out/'probe.mjs').write_text(js)
try:
 launch('controls',17864,controls);launch('legacy',17865,cfg['graph'])
 browser=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch/aevora_gen1_5_2_evidence/Gen1.5.2-20261014T065322Z-01fb65a2-eac4-4ce4-a468-9fe5de1a8567-prearchive-review/browser_runtime')
 assert record('v4-live-browser-supplement',['node',str(out/'probe.mjs')],env={'PLAYWRIGHT_BROWSERS_PATH':str(browser)})==0
finally:
 edgeout=E/'05_product/live_browser_ablation'
 if (edgeout/'CUT.json').exists() and not (edgeout/'RESTORED.json').exists():record('v4-browser-edge-emergency-restore',runtime(str(E/'v4_live_edge.py'),'restore'))
 for name,p,stdout,stderr,argv,begin,label in procs:
  stopped=subprocess.run(['docker','stop','--time','10',name],capture_output=True);code=p.wait(30);stdout.close();stderr.close();write(out/(label+'-command.json'),{'argv':argv,'started_at':begin,'ended_at':now(),'exit_code':code,'stop_exit':stopped.returncode})
print('V4 browser supplementary real states PASS')
