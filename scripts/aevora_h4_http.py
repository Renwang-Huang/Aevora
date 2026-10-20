"""Actual Uvicorn TCP/HTTP gate, public projection scan, no model calls or UI."""
import os
from hashlib import sha256
import json
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request
import urllib.error
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now,launch


def main(label='actual-http'):
    a=archive();out=a/'g2'/label;out.mkdir(mode=0o700)
    with socket.socket() as reserved:reserved.bind(('127.0.0.1',17804))
    pin=digest(ROOT/'examples/observatory/hero_scenario_contract.json')
    argv=launch('-m','aevora_observatory.server','--replay-root',str(ROOT/'examples/observatory'),'--replay-sha256',pin,'--activity-root',str(a),'--port','17804')
    stdout=(out/'server-stdout.log').open('wb');stderr=(out/'server-stderr.log').open('wb');started=now()
    proc=subprocess.Popen(argv,cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
    receipts=[];checks=[]
    cfg=json.loads((a/'CONFIG.json').read_text());paths=[Path(cfg['password_file']),Path(os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH', str(Path.home()/'.config/orderflow/gateway_api_key')))]
    patterns=[]
    for p in paths:
        value=p.read_bytes().strip();patterns.extend([value,sha256(value).hexdigest().encode(),sha256(value).digest()])
    def get(path,method='GET',headers=None):
        req=urllib.request.Request('http://127.0.0.1:17804'+path,method=method,headers=headers or {})
        begin=now()
        try:
            with urllib.request.urlopen(req,timeout=20) as r:code=r.status;raw=r.read(4*1024*1024+1);h=dict(r.headers)
        except urllib.error.HTTPError as e:code=e.code;raw=e.read(4*1024*1024+1);h=dict(e.headers)
        if len(raw)>4*1024*1024:raise ValueError('HTTP response size budget exceeded')
        if any(p in raw for p in patterns):raise ValueError('Actual credential/individual digest in PUBLIC response')
        if any(p in raw for p in [b'/home/private-user/.config/',b'AEVORA_RUN_TOKEN',b'raw_mcp_payload']):raise ValueError('Private projection field exposed')
        n=len(receipts)+1;d=out/('request-'+str(n));d.mkdir();(d/'response.json').write_bytes(raw)
        row={'method':method,'path':path,'status':code,'started_at':begin,'ended_at':now(),'headers':h,'response_sha256':digest(d/'response.json'),'bytes':len(raw)}
        write(d/'request.json',row);receipts.append(row);return code,json.loads(raw)
    def check(label,ok,actual):
        checks.append({'name':label,'status':'PASS' if ok else 'FAIL','actual':actual})
        if not ok:raise ValueError('HTTP control failed: '+label)
    try:
        deadline=time.monotonic()+15
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:17804/',timeout=1) as r:
                    if r.status==200:break
            except OSError:
                if proc.poll() is not None or time.monotonic()>deadline:raise ValueError('Actual HTTP server not ready')
                time.sleep(.05)
        for case in ['case-a','case-b','case-c']:
            code,v=get('/api/overview?mode=REPLAY&case='+case);check('actual_replay_'+case,code==200 and v['mode']=='REPLAY' and v['contract_sha256']==pin,{'status':code,'mode':v['mode'],'case':v['case']['case_id']})
        for context,expected in [('threads','APPLY'),('workers','ABSTAIN'),('unknown','VERIFY')]:
            code,v=get('/api/overview?mode=LIVE&case=case-b&context='+context)
            check('actual_live_'+context,code==200 and v['mode']=='LIVE' and v['decisions'][0]['decision']==expected,{'status':code,'actual_decision':v['decisions'][0]['decision'],'context_authority':v['context_authority']})
        code,v=get('/api/proof/origin');check('public_origin_proof',code==200 and v['data']['test_counts']['passed']==14 and len(v['data']['children'])==3,{'status':code,'actual_counts':v['data']['test_counts']})
        code,v=get('/api/cypher',method='POST');check('admin_write_denied',code==403,v)
        code,v=get('/api/overview?path=/etc/passwd');check('arbitrary_file_denied',code==400,v)
        code,v=get('/api/overview',headers={'Origin':'https://unrelated.example'});check('foreign_origin_denied',code==403,v)
        code,v=get('/api/proof/private-manifest');check('private_artifact_denied',code==403,v)
        check('actual_response_credential_scan',True,{'actual_credential_classes':len(paths),'matches':0,'individual_secret_fingerprints_archived':False})
    finally:
        proc.send_signal(signal.SIGTERM)
        try:exitcode=proc.wait(10)
        except subprocess.TimeoutExpired:proc.kill();exitcode=proc.wait(5)
        stdout.close();stderr.close()
        deadline=time.monotonic()+5;port_closed=False
        while time.monotonic()<deadline:
            try:
                with socket.create_connection(('127.0.0.1',17804),timeout=.2):pass
            except OSError:port_closed=True;break
            time.sleep(.05)
        write(out/'server-command.json',{'argv':argv,'started_at':started,'ended_at':now(),'exit_code':exitcode,
            'stdout_sha256':digest(out/'server-stdout.log'),'stderr_sha256':digest(out/'server-stderr.log'),'role':'Actual owned loopback read-only API; no model calls',
            'owner_requested_signal':'SIGTERM','process_boundary':'bubblewrap --die-with-parent','owned_port_closed':port_closed})
    check('controlled_owner_stop_closes_listener',exitcode in [0,-signal.SIGTERM] and port_closed,{'actual_exit':exitcode,'owner_requested_signal':'SIGTERM','owned_port_closed':port_closed,'classification':'CONTROLLED_OWNER_STOP; not an autonomous server error or claimed graceful inner exit0'})
    result={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'requests':receipts,'model_calls':0,'ui_present':False}
    write(out/'RESULT.json',result);print(json.dumps({'status':result['status'],'checks':len(checks),'requests':len(receipts),'server_exit':exitcode}));return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='actual-http');args=p.parse_args()
    if not args.label.replace('-','').isalnum():raise ValueError('Unique simple label required')
    raise SystemExit(main(args.label))
