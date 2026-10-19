"""Actual installed-Core expiry and unavailable-DB controls, no model calls."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from scripts.aevora_h4_audit import archive,write,digest,now


def main(label='connection-boundary-controls',installation='clean-onboarding-02'):
    a=archive();out=a/'g1'/label;out.mkdir(mode=0o700)
    python=a/'g1'/installation/'venv/bin/python';project=a/'g1'/installation/'ordinary-project'
    env={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','PYTHONHOME']};checks=[];commands=[]
    def command(label,argv,environment=env):
        started=now();r=subprocess.run(list(map(str,argv)),cwd=project,env=environment,capture_output=True,timeout=30)
        d=out/label;d.mkdir();(d/'stdout.log').write_bytes(r.stdout);(d/'stderr.log').write_bytes(r.stderr)
        row={'argv':list(map(str,argv)),'exit_code':r.returncode,'started_at':started,'ended_at':now(),
             'stdout_sha256':digest(d/'stdout.log'),'stderr_sha256':digest(d/'stderr.log')};write(d/'command.json',row);commands.append(row);return r
    def check(name,ok,data):
        row={'name':name,'status':'PASS' if ok else 'FAIL','actual':data};checks.append(row)
        if not ok:write(out/'FAILURE.json',row);raise ValueError('Actual connection boundary failed')
    with tempfile.TemporaryDirectory(prefix='aevora-h4-expiry-') as temp:
        private=Path(temp);private.chmod(0o700);cap=private/'grant.json';sock=private/'mcp.sock'
        argv=[str(python),'-I','-m','aevora','serve','--run-id','h4-explicit-expiry','--context',str(project/'context.json'),
              '--socket',str(sock),'--capability-file',str(cap),'--events',str(out/'actual_mcp_events.jsonl'),'--capability-ttl','1']
        started=now();stdout=(out/'serve-stdout.log').open('wb');stderr=(out/'serve-stderr.log').open('wb')
        p=subprocess.Popen(argv,cwd=project,env=env,stdout=stdout,stderr=stderr)
        deadline=time.monotonic()+15
        while not cap.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        if not cap.exists():p.terminate();p.wait(10);raise ValueError('Expiry Host did not start')
        stale=private/'stale.json';raw=cap.read_bytes();stale.write_bytes(raw);stale.chmod(0o600)
        token=json.loads(raw)['AEVORA_RUN_TOKEN']
        try:code=p.wait(10)
        finally:
            if p.poll() is None:p.terminate();p.wait(10)
            stdout.close();stderr.close()
        write(out/'serve-command.json',{'argv':argv,'exit_code':code,'started_at':started,'ended_at':now(),
            'stdout_sha256':digest(out/'serve-stdout.log'),'stderr_sha256':digest(out/'serve-stderr.log')})
        check('explicit_ttl_revokes_owner',code==0 and not cap.exists() and not sock.exists(),{'exit_code':code,'capability_removed':not cap.exists(),'socket_removed':not sock.exists()})
        r=command('expired-connector',[python,'-I','-m','aevora.mcp_connect','--capability-file',stale],{'PATH':'/usr/bin:/bin','HOME':str(private)})
        check('expired_connector_denied',r.returncode==1 and b'scoped connection unavailable or revoked' in r.stderr,{'actual_exit':r.returncode})
        check('ephemeral_token_not_archived',all(token.encode() not in f.read_bytes() for f in out.rglob('*') if f.is_file()),{'actual_capability_value_matches':0})
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
        r=command('owned-disconnected-graph',[python,'-I','-m','aevora','health'],{**env,'AEVORA_FALKORDB_PORT':str(port)})
        check('actual_graph_unavailable_no_fallback',r.returncode==2 and b'GraphUnavailable' in r.stderr,{'actual_exit':r.returncode,'own_non_listening_port':port,'fallback':False})
    write(out/'RESULT.json',{'status':'PASS','checks':checks,'commands':commands,'model_calls':0,'scope':'Actual explicit local TTL/closed owned port; not a fixed Codex execution timeout.'})
    print(json.dumps({'status':'PASS','checks':len(checks),'model_calls':0}));return 0


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',default='connection-boundary-controls');p.add_argument('--installation',default='clean-onboarding-02');args=p.parse_args()
    if not all(v.replace('-','').isalnum() for v in [args.label,args.installation]):raise ValueError('Simple unique labels required')
    raise SystemExit(main(args.label,args.installation))
