"""Actual official workspace-write boundary probe; no model/Agent grade."""
from audit import *
from benchmark.runner import BenchmarkRunner
from benchmark.participant import build_participant
from benchmark.participant_sandbox import participant_command
out=E/'05_security/native-state';out.mkdir(parents=True)
rep=BenchmarkRunner(out/'runs').prepare('D',variant='v01');run=out/'runs'/rep['run_id'];w=build_participant(run/'workspace',run/'participant');state=run/'state';state.mkdir();(state/'sessions').mkdir();(state/'sessions/canary.jsonl').write_text('HOST_CREATED_CANARY_NOT_AN_OFFICIAL_ROLLOUT\n')
code='''import pathlib,json,os
result={}
for name,path in [('native_state','/codex-state/sessions/canary.jsonl'),('forged_rollout','/codex-state/sessions/forged.jsonl'),('workspace','/workspace/boundary-write-canary')]:
 try:pathlib.Path(path).write_text('PROBE_WRITE');result[name]={'writable':True}
 except OSError as e:result[name]={'writable':False,'errno':e.errno}
print(json.dumps(result))
assert not result['native_state']['writable'] and not result['forged_rollout']['writable'] and result['workspace']['writable']
'''
cmd=participant_command(w,state,Path(os.environ['ORDERFLOW_CODEX_BINARY']),['/opt/codex/codex','sandbox','-c','sandbox_mode="workspace-write"','-c','approval_policy="never"','--','/usr/bin/python3.12','-I','-c',code],network_isolated=True)
import subprocess,time
start=now();r=subprocess.run(cmd,capture_output=True,timeout=30)
(out/'stdout.json').write_bytes(r.stdout);(out/'stderr.log').write_bytes(r.stderr)
write(out/'RECEIPT.json',{'at':start,'argv':cmd,'exit':r.returncode,'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'scope':'ACTUAL_OFFICIAL_NATIVE_COMMAND_SANDBOX_NOT_A_NEW_MODEL_SESSION','source':'CURRENT_DYNAMIC','native_state_unchanged':(state/'sessions/canary.jsonl').read_text()=='HOST_CREATED_CANARY_NOT_AN_OFFICIAL_ROLLOUT\n'})
print(r.stdout.decode());assert r.returncode==0
