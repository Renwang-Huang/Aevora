"""Installed Core CLI/official MCP SDK in a clean ordinary directory.

No OrderFlow Runner, Registry, Evaluator or model request. Scoped capabilities
stay in a private temporary directory and only sanitized headers are archived.
"""
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import tempfile
import time
import uuid
from types import SimpleNamespace
from scripts.aevora_h3_audit import archive,write,digest,now
from scripts.aevora_h2_security import RPCClient


def main():
    A=archive();out=A/'g2/core-connection';out.mkdir(parents=True,mode=0o700)
    installation=A/'g2/standalone-install';python=installation/'venv/bin/python';wheel=next((installation/'dist').glob('*.whl'))
    env={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','PYTHONHOME']}
    cwd=out/'ordinary-project';cwd.mkdir();context={'concurrency_scope':'single_process_threads','shared_state_kind':'sqlite_file',
        'synchronization_scope':'shared_process_object','transaction_guarantees':'sqlite_atomic_write_transactions','worker_count_known':True}
    write(cwd/'context.json',context);commands=[];checks=[]
    def check(name,value,actual):
        checks.append({'name':name,'status':'PASS' if value else 'FAIL','actual':actual})
        write(out/(name+'.json'),actual)
        if not value:raise ValueError('Standalone connection check failed: '+name)
    def cmd(argv,environment=env):
        start=now();r=subprocess.run(list(map(str,argv)),cwd=cwd,env=environment,capture_output=True,timeout=60)
        n=len(commands)+1;d=out/('command-'+str(n));d.mkdir();(d/'stdout.log').write_bytes(r.stdout);(d/'stderr.log').write_bytes(r.stderr)
        commands.append({'argv':list(map(str,argv)),'exit_code':r.returncode,'cwd':str(cwd),'started_at':start,'ended_at':now(),
                         'stdout_sha256':digest(d/'stdout.log'),'stderr_sha256':digest(d/'stderr.log')});write(d/'command.json',commands[-1]);return r
    r=cmd([python,'-m','pip','install','--no-deps',wheel]);check('reinstall_public_core',r.returncode==0,commands[-1])
    r=cmd([python,'-I','-c',"import importlib.util; assert importlib.util.find_spec('benchmark') is None; assert importlib.util.find_spec('integrations') is None; print('NO_BENCHMARK_DEPENDENCY')"])
    check('core_environment_has_no_benchmark',r.returncode==0,commands[-1])
    empty='aevora_h3_external_empty_'+uuid.uuid4().hex;emptyenv={**env,'AEVORA_FALKORDB_GRAPH':empty}
    r=cmd([python,'-I','-m','aevora','init'],emptyenv);check('empty_real_graph_initialized',r.returncode==0,commands[-1])
    sessions=[]
    with tempfile.TemporaryDirectory(prefix='aevora-h3-core-') as temporary:
        tmp=Path(temporary);tmp.chmod(0o700)
        def start(label,environment):
            sock=tmp/'mcp.sock';cap=tmp/'cap.json';events=out/(label+'-mcp.jsonl')
            argv=[str(python),'-I','-m','aevora','serve','--run-id','h3-ordinary-core-project','--context',str(cwd/'context.json'),
                '--socket',str(sock),'--capability-file',str(cap),'--events',str(events),'--enable-proposals']
            stdout=(out/(label+'-stdout.log')).open('wb');stderr=(out/(label+'-stderr.log')).open('wb')
            p=subprocess.Popen(argv,cwd=cwd,env=environment,stdout=stdout,stderr=stderr)
            deadline=time.monotonic()+15
            while not cap.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
            if not cap.exists():p.terminate();p.wait(10);stdout.close();stderr.close();raise ValueError('Actual Core serve startup failed')
            token=json.loads(cap.read_text())['AEVORA_RUN_TOKEN']
            owner=SimpleNamespace(socket_path=sock,run_id='h3-ordinary-core-project')
            return p,stdout,stderr,token,owner,cap,argv
        def stop(s,label):
            p,stdout,stderr,token,owner,cap,argv=s;p.send_signal(signal.SIGTERM);exitcode=p.wait(15);stdout.close();stderr.close()
            sessions.append({'label':label,'argv':argv,'exit_code':exitcode,'capability_removed':not cap.exists(),'socket_removed':not owner.socket_path.exists()})
            check(label+'_revoked_and_cleaned',exitcode==0 and not cap.exists() and not owner.socket_path.exists(),sessions[-1])
            check(label+'_known_capability_not_archived',all(token.encode() not in f.read_bytes() for f in out.iterdir() if f.is_file()),{'known_capability_value_found':False})
        first=start('first',env)
        try:
            c=RPCClient(first[4],first[3],out/'first-client.jsonl');c.initialize()
            answer=c.tool('resolve_experience',{'task_context':{}});actual=answer['result']['structuredContent']
            check('installed_core_official_sdk_query',actual['status']=='AVAILABLE' and bool(actual['candidates']),answer)
            selected=actual['candidates'][-1]['experience_id'];bundle=c.tool('build_evidence_bundle',{'experience_id':selected,'query_id':actual['query_id']})
            check('installed_core_official_sdk_bundle',not bundle['result'].get('isError'),bundle)
            decision=c.tool('record_decision',{'decision':{'query_id':actual['query_id'],'experience_id':selected,'decision':'VERIFY','reason':'Ordinary project must investigate before adopting a sourced principle.','verification_steps':['Inspect actual source and run own tests.']}})
            check('decision_remains_untrusted',decision['result']['structuredContent']['status']=='RECORDED_UNTRUSTED',decision)
            c.close()
        finally:stop(first,'first')
        second=start('reconnected',env)
        try:
            denied=False
            try:
                old=RPCClient(second[4],first[3],out/'old-cap-client.jsonl')
                # The broker's framed rejection is authoritative; do not try
                # to treat a closed unauthorized channel as an SDK session.
                denied=old.ack.get('aevora_transport')=='REJECTED'
                old.close()
            except (ValueError,OSError,EOFError):denied=True
            check('old_capability_cannot_reconnect',denied,{'previous_capability_rejected':denied,'tokens_differ':second[3]!=first[3]})
            c=RPCClient(second[4],second[3],out/'reconnected-client.jsonl');c.initialize();answer=c.tool('resolve_experience',{'task_context':{}})
            check('new_connection_queries_actual_graph',answer['result']['structuredContent']['status']=='AVAILABLE',answer);c.close()
        finally:stop(second,'reconnected')
        third=start('empty',emptyenv)
        try:
            c=RPCClient(third[4],third[3],out/'empty-client.jsonl');c.initialize();answer=c.tool('resolve_experience',{'task_context':{}})
            check('empty_graph_has_no_static_fallback',answer['result']['structuredContent']['candidates']==[],answer);c.close()
        finally:stop(third,'empty')
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
            r=cmd([python,'-I','-m','aevora','health'],{**env,'AEVORA_FALKORDB_PORT':str(port)})
            check('owned_disconnected_database_fails_closed',r.returncode!=0 and b'GraphUnavailable' in r.stderr,{'command':commands[-1],'owned_non_listening_port':port})
    write(out/'RESULT.json',{'status':'PASS','checks':checks,'commands':commands,'sessions':sessions,'native_model_calls':0,
         'authority':'REAL_CLEAN_PUBLIC_CORE_AND_OFFICIAL_MCP_SDK; NOT_AN_AGENT_CHALLENGE','graph':env['AEVORA_FALKORDB_GRAPH'],'at':now()})
    print(json.dumps({'status':'PASS','checks':len(checks),'model_calls':0}));return 0


if __name__=='__main__':raise SystemExit(main())
