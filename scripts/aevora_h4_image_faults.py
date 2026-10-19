"""Actual public image, owned unavailable DB port; LIVE never uses Replay."""
import json,socket,subprocess,time,urllib.request,urllib.error
from scripts.aevora_h4_audit import archive,write,digest,now

def main():
    A=archive();out=A/'g5/public-image-database-disconnected';out.mkdir(mode=0o700);cfg=json.loads((A/'g5/fresh-user-01/CONFIG.json').read_text())
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));unavailable=reservation.getsockname()[1]
        name='aevora-h4-db-disconnected-probe'
        argv=['docker','run','--rm','--name',name,'--network','host','--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--mount','type=bind,src='+cfg['password_file']+',dst=/run/secrets/db,readonly','--env','AEVORA_FALKORDB_PASSWORD_FILE=/run/secrets/db','--env','AEVORA_FALKORDB_PORT='+str(unavailable),'--env','AEVORA_FALKORDB_GRAPH=aevora_product','aevora-h4-local:final','--replay-root','/opt/aevora/h4','--replay-sha256','c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776','--port','17807']
        begin=now();stdout=(out/'server-stdout.log').open('wb');stderr=(out/'server-stderr.log').open('wb');proc=subprocess.Popen(argv,stdout=stdout,stderr=stderr);responses=[]
        try:
            deadline=time.monotonic()+20
            while True:
                try:
                    with urllib.request.urlopen('http://127.0.0.1:17807/',timeout=1) as r:
                        if r.status==200:break
                except OSError:
                    if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Public fault-control server unavailable')
                    time.sleep(.05)
            for mode in ['LIVE','REPLAY']:
                started=now()
                try:
                    with urllib.request.urlopen('http://127.0.0.1:17807/api/overview?case=case-b&mode='+mode,timeout=10) as r:status=r.status;body=r.read()
                except urllib.error.HTTPError as e:status=e.code;body=e.read()
                (out/(mode+'-response.json')).write_bytes(body);v=json.loads(body);responses.append({'mode':mode,'status':status,'response_sha256':digest(out/(mode+'-response.json')),'started_at':started,'ended_at':now()})
                if mode=='LIVE':assert status==503 and v['status']=='UNAVAILABLE' and v['fallback'] is False and v['error']=='GraphUnavailable'
                else:assert status==200 and v['mode']=='REPLAY'
        finally:
            stopped=subprocess.run(['docker','stop','--time','20',name],capture_output=True);code=proc.wait(30);stdout.close();stderr.close()
            write(out/'server-command.json',{'argv':argv,'exit_code':code,'started_at':begin,'ended_at':now(),'owner_stop_argv':['docker','stop','--time','20',name],'owner_stop_exit':stopped.returncode,'stdout_sha256':digest(out/'server-stdout.log'),'stderr_sha256':digest(out/'server-stderr.log')})
        assert stopped.returncode==code==0
    write(out/'RESULT.json',{'status':'PASS','responses':responses,'failure':'Actual non-listening OS port owned by this probe; existing DB and running Session untouched','model_calls':0,'at':now()});print(json.dumps({'status':'PASS','responses':len(responses),'model_calls':0}));return 0

if __name__=='__main__':raise SystemExit(main())
