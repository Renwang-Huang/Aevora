#!/usr/bin/env python3
"""Real outer/native Participant MCP and path denial probes (no model calls)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from benchmark.participant import build_participant
from benchmark.participant_sandbox import participant_command
from benchmark.runner import BenchmarkRunner
from integrations.aevora import AevoraRuntimeBridge

ROOT=Path(__file__).resolve().parents[1]

CODE='''import json,os,subprocess,socket,sys
authority=json.loads(sys.stdin.buffer.readline(8192))
os.environ.update(AEVORA_RUN_TOKEN=authority['token'],AEVORA_RUN_ID=authority['run_id'])
paths=PATHS
denied={}
for label,path in paths.items():
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK);os.close(fd);denied[label]=False
 except OSError:denied[label]=True
assert all(denied.values()),denied
assert os.path.isfile('/workspace/app/service.py')
assert not os.path.exists('/aevora-channel/../maintainer')
s=None
try:
 s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1',16379));graph_port_denied=False
except OSError:graph_port_denied=True
finally:
 if s is not None:s.close()
assert graph_port_denied
if MODE=='native':
 connection=None
 try:
  connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);connection.connect('/aevora-channel/mcp.sock');native_mcp_denied=False
 except OSError:native_mcp_denied=True
 finally:
  if connection is not None:connection.close()
 assert native_mcp_denied,'Native business command unexpectedly accessed host capability'
 print(json.dumps({'denied_paths':denied,'public_source_access':True,'graph_tcp_denied':True,'mcp_command_socket_denied':True,'scope':'Native command has no network capability; MCP client is the native Runtime outside command sandbox','model_calls':0}))
 sys.exit(0)
p=subprocess.Popen(['/usr/bin/python3.12','-I','-B','/aevora_mcp_proxy.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def call(value):
 p.stdin.write(json.dumps(value).encode()+b'\\n');p.stdin.flush()
 line=p.stdout.readline();assert line,'Missing SDK response'
 response=json.loads(line);assert response.get('id')==value.get('id'),response
 return response
init=call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Aevora physical isolation probe','version':'1.0'}}})
assert init['result']['serverInfo']['name']=='Aevora'
p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\\n');p.stdin.flush()
listed=call({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
tools={t['name'] for t in listed['result']['tools']}
assert tools=={'resolve_experience','build_evidence_bundle','record_decision'}
resolved=call({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'resolve_experience','arguments':{'task_context':{}}}})
assert not resolved['result'].get('isError'),resolved
result=resolved['result']['structuredContent']
assert result['run_id']==authority['run_id'] and result['status']=='AVAILABLE'
candidate=next(c for c in result['candidates'] if c['decision']=='APPLY')
bundled=call({'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'build_evidence_bundle','arguments':{'experience_id':candidate['experience_id']}}})
assert not bundled['result'].get('isError'),bundled
decision=call({'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'record_decision','arguments':{'decision':{'query_id':result['query_id'],'experience_id':candidate['experience_id'],'decision':'VERIFY','reason':'Physical boundary probe, no Agent adoption or business outcome claimed','verification_steps':['No model used; this is an isolation protocol test']}}}})
assert not decision['result'].get('isError'),decision
assert decision['result']['structuredContent']['status']=='RECORDED_UNTRUSTED'
forbidden=call({'jsonrpc':'2.0','id':6,'method':'tools/call','params':{'name':'record_decision','arguments':{'decision':{'query_id':result['query_id'],'experience_id':candidate['experience_id'],'decision':'APPLY','reason':'forgery','verified':True,'verdict':'PASS'}}}})
assert forbidden['result'].get('isError') is True
p.stdin.close();p.wait(timeout=5)
print(json.dumps({'denied_paths':denied,'public_source_access':True,'graph_tcp_denied':graph_port_denied,'mcp_server':init['result']['serverInfo'],'tools':sorted(tools),'query_id':result['query_id'],'decision_id':decision['result']['structuredContent']['decision_id'],'forged_outcome_claim_rejected':True,'source':'Real Participant stdlib proxy to official host MCP SDK to real FalkorDB','model_calls':0}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    runner=BenchmarkRunner(args.output/'runs');prepared=runner.prepare('D')
    run_id=prepared['run_id'];run=args.output/'runs'/run_id
    participant=build_participant(run/'workspace',run/'participant')
    manifest=json.loads((participant/'public.json').read_text())
    targets={'hidden_tests':ROOT/'evaluator/hidden_tests','reference_patch':ROOT/'evaluator/reference_patches/D-v01.diff',
        'private_manifest':ROOT/'evaluator/private_manifests/D.json','private_labels':ROOT/'evaluator/private_labels/episode_d_applicability.json',
        'maintainer_source':ROOT/'app/service.py','historical_report':ROOT/'runs/339f7d73-29df-4242-8920-9e566bce8a9c/evaluation_report.json',
        'host_governance':ROOT/'aevora_core/src/aevora/orderflow_outcome_bridge.py','host_gateway_key':Path(os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH', str(Path.home()/'.config/orderflow/gateway_api_key'))),
        'host_db_key':Path(os.environ.get('AEVORA_FALKORDB_PASSWORD_FILE', str(Path.home()/'.config/aevora/falkordb.password'))),'trusted_launcher_db_key':Path('/maintainer/aevora-db.password'),
        'trusted_launcher_gateway_key':Path('/maintainer/gateway.key')}
    paths={name:str(path) for name,path in targets.items()}
    paths.update({'proc_root_'+name:'/proc/1/root'+str(path) for name,path in targets.items()})
    binary=Path(os.environ['ORDERFLOW_CODEX_BINARY']);rows=[]
    for label in ('outer','native'):
        code=CODE.replace('PATHS',repr(paths)).replace('MODE',repr(label))
        state=run/('probe-state-'+label);state.mkdir(mode=0o700)
        with AevoraRuntimeBridge(run_id,manifest,args.output/label) as bridge:
            command=['/usr/bin/python3.12','-I','-c',code]
            if label=='native':command=['/opt/codex/codex','sandbox','-c','sandbox_mode="workspace-write"','-c','approval_policy="never"','--',*command]
            argv=participant_command(participant,state,binary,command,network_isolated=True,
                aevora_socket=bridge.socket_path,aevora_proxy=bridge.proxy_path)
            result=subprocess.run(argv,input=json.dumps({'token':bridge.run_token,'run_id':run_id}).encode()+b'\n',capture_output=True,timeout=90)
            (args.output/(label+'.stdout.log')).write_bytes(result.stdout)
            (args.output/(label+'.stderr.log')).write_bytes(result.stderr)
            rows.append({'label':label,'argv':argv,'exit_code':result.returncode,'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),
                'stderr_sha256':hashlib.sha256(result.stderr).hexdigest(),'observations':json.loads(result.stdout) if result.stdout else None})
        rows[-1]['aevora']=bridge.metadata
        cleanup=bridge.metadata['broker'];assert cleanup['active_connections']==cleanup['active_sdk_children']==0 and all(cleanup[k] for k in ('token_revoked','socket_unlinked','handler_cleanup_complete','server_thread_stopped'))
        assert result.returncode==0,rows[-1]
    summary={'gate':'G3_PHYSICAL_ISOLATION','status':'PASS','model_calls':0,'run_id':run_id,'probes':rows,
        'scope':'Real namespace/native file and MCP capability boundary; not total adversarial/VM attestation'}
    with (args.output/'summary.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','probes':len(rows),'run_id':run_id,'model_calls':0}))
    return 0


if __name__=='__main__':raise SystemExit(main())
