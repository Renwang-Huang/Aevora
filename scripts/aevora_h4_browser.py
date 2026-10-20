"""Actual standalone Chromium against public loopback API + fresh owned empty graph."""
import argparse,json,signal,socket,subprocess,time,uuid,urllib.request
from pathlib import Path
from scripts.aevora_h4_audit import ROOT,archive,record,launch,write,digest,now

def main(label):
    a=archive();out=a/'g3'/label;out.mkdir(mode=0o700);name='aevora_h4_browser_empty_'+uuid.uuid4().hex
    create="from aevora.graph_repository import GraphRepository; r=GraphRepository.from_environment(); r.initialize(); print(r.state_fingerprint()); r.close()"
    rc=record(a,label+'-empty-graph-init',launch('-c',create,graph=name))
    if rc:raise ValueError('Actual empty graph init failed')
    argv=launch('-m','aevora_observatory.server','--replay-root',ROOT/'examples/observatory','--replay-sha256',digest(ROOT/'examples/observatory/hero_scenario_contract.json'),'--port','17805',graph=name)
    begin=now();stdout=(out/'server-stdout.log').open('wb');stderr=(out/'server-stderr.log').open('wb');proc=subprocess.Popen(argv,cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
    try:
        deadline=time.monotonic()+20
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:17805/',timeout=1) as r:
                    if r.status==200:break
            except OSError:
                if proc.poll() is not None or time.monotonic()>deadline:raise ValueError('Actual empty graph server failed')
                time.sleep(.05)
        rc=record(a,label+'-chromium',['env','PLAYWRIGHT_BROWSERS_PATH='+str(ROOT/'aevora_validation/h4_browser_runtime'),'AEVORA_BROWSER_OUTPUT='+str(out/'browser'),'AEVORA_EMPTY_BROWSER_URL=http://127.0.0.1:17805','node','console/browser/validate.mjs'])
    finally:
        proc.send_signal(signal.SIGTERM)
        try:code=proc.wait(10)
        except subprocess.TimeoutExpired:proc.kill();code=proc.wait(5)
        stdout.close();stderr.close()
        write(out/'server-command.json',{'argv':argv,'started_at':begin,'ended_at':now(),'exit_code':code,'owner_requested_signal':'SIGTERM','stdout_sha256':digest(out/'server-stdout.log'),'stderr_sha256':digest(out/'server-stderr.log'),'graph':name})
        cleanup="from aevora.graph_repository import GraphRepository; r=GraphRepository.from_environment(); r._graph.delete(); r.close(); print('OWNED_EMPTY_GRAPH_REMOVED')"
        record(a,label+'-empty-graph-cleanup',launch('-c',cleanup,graph=name))
    result=json.loads((out/'browser/RESULT.json').read_text());files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()};write(out/'RECEIPT.json',{'status':result['status'],'files':files,'browser_checks':len(result['checks']),'model_calls':0,'at':now()});return rc

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);args=p.parse_args()
    if not args.label.replace('-','').isalnum():raise ValueError('Unique simple label required')
    raise SystemExit(main(args.label))
