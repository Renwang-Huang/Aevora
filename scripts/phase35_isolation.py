"""Offline installed CLI command sandbox, file probes, owned local listener."""
from pathlib import Path
import datetime, hashlib, json, os, socket, subprocess, sys, threading
ROOT=Path(__file__).resolve().parents[1]; HERE=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT))
from benchmark.participant import build_participant
from benchmark.participant_sandbox import participant_command as _participant_command
def participant_command(*args, **kwargs):
 return _participant_command(*args,network_isolated=True,**kwargs)
from benchmark.sandbox import sandbox_command, runtime_python

OUT=HERE/'isolation';OUT.mkdir();state=OUT/'state';state.mkdir()
participant=build_participant(ROOT/'runs/339f7d73-29df-4242-8920-9e566bce8a9c/workspace',OUT/'participant')
binary=Path(os.environ['ORDERFLOW_CODEX_BINARY'])
auth=OUT/'synthetic-auth-canary'; auth.write_text('synthetic auth boundary probe'); auth.chmod(0o600)
targets={'hidden_tests':ROOT/'evaluator/hidden_tests','private_manifest':ROOT/'evaluator/private_manifests/A.json',
 'reference_patch':ROOT/'evaluator/reference_patches/A-v01.diff','maintainer_source':ROOT/'app/service.py',
 'other_run':ROOT/'runs/666f334a-5335-419d-bcd4-45797d819c8d/evaluation_report.json',
 'maintainer_modules':ROOT/'benchmark','host_user_directory':Path.home(),
 'trusted_auth':auth,'host_auth':Path(os.environ.get('ORDERFLOW_CODEX_AUTH_PATH', str(Path.home()/'.codex/auth.json'))),
 'new_evidence':HERE/'snapshots/before.json'}
existence={k:p.exists() for k,p in targets.items()}
targets={k:str(p) for k,p in targets.items()}
targets.update({'proc_root_'+k:'/proc/1/root'+v for k,v in list(targets.items())})
targets['traversal_source']='/workspace/../../'+str(ROOT/'app/service.py').lstrip('/')
probe='''import os,json,pathlib
targets=TARGETS
observations={}
for label,path in targets.items():
 try:
  if pathlib.Path(path).is_dir():os.listdir(path)
  else:
   fd=os.open(path,os.O_RDONLY);os.close(fd)
  observations[label]={'readable':True,'errno':None}
 except OSError as e:observations[label]={'readable':False,'errno':e.errno}
print(json.dumps({'paths':observations,'public_source':pathlib.Path('/workspace/app/service.py').is_file(),
 'cwd':os.getcwd(),'HOME':os.environ.get('HOME'),'CODEX_HOME':os.environ.get('CODEX_HOME'),
 'pid_namespace':os.readlink('/proc/self/ns/pid'),'mount_namespace':os.readlink('/proc/self/ns/mnt'),
 'mounts':[line.split()[4] for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines()]}))
assert all(not v['readable'] for v in observations.values())
'''.replace('TARGETS',repr(targets))
records=[]
def run(label,argv):
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
 out,err=OUT/(label+'.stdout.log'),OUT/(label+'.stderr.log')
 out.write_text(p.stdout);err.write_text(p.stderr)
 try:result=json.loads(p.stdout)
 except ValueError:result=None
 record={'label':label,'argv':argv,'started_at':start,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'exit_code':p.returncode,'stdout':str(out.relative_to(HERE)),'stderr':str(err.relative_to(HERE)),
 'stdout_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'stderr_sha256':hashlib.sha256(err.read_bytes()).hexdigest(),
 'result':result,'evidence_grade':'B'}
 records.append(record);(OUT/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
 return record
version=run('installed-codex-version',participant_command(participant,state,binary,['/opt/codex/codex','--version']))
outer=run('outer-file-probe',participant_command(participant,state,binary,[runtime_python(),'-I','-c',probe]))
inner=run('native-file-probe',participant_command(participant,state,binary,
 ['/opt/codex/codex','sandbox','-c','sandbox_mode="workspace-write"','-c','approval_policy="never"','--',runtime_python(),'-I','-c',probe]))
worker=run('candidate-file-probe',sandbox_command(participant,[runtime_python(),'-I','-c',probe]))

listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(8);listener.settimeout(.2)
port=listener.getsockname()[1];stop=threading.Event();accepted=[]
def serve():
 while not stop.is_set():
  try:conn,_=listener.accept();accepted.append(True);conn.close()
  except socket.timeout:pass
  except OSError:break
thread=threading.Thread(target=serve);thread.start()
code=f'''import socket,json
try:
 s=socket.socket();s.settimeout(2);s.connect(('127.0.0.1',{port}));s.close();result={{'connected':True}}
except OSError as e:result={{'connected':False,'error_type':type(e).__name__,'errno':e.errno}}
print(json.dumps(result))
'''
try:
 for label,cmd in (
  ('outer-owned-network',participant_command(participant,state,binary,[runtime_python(),'-I','-c',code])),
  ('native-owned-network',participant_command(participant,state,binary,['/opt/codex/codex','sandbox','-c','sandbox_mode="workspace-write"','-c','approval_policy="never"','--',runtime_python(),'-I','-c',code])),
  ('candidate-owned-network',sandbox_command(participant,[runtime_python(),'-I','-c',code]))):run(label,cmd)
finally:stop.set();listener.close();thread.join(timeout=2)
summary={'scope':'fresh offline probes with current installed CLI; not a new Lead or child model session',
 'live_model_calls':0,'targets_exist_in_trusted_wrapper':existence,
 'host_auth_existence_in_wrapper':'NOT_MOUNTED; existence on host checked separately',
 'credential_content_read':False,'auth_file_mode':oct(auth.stat().st_mode&0o777),
 'codex_binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
 'owned_listener_address':'127.0.0.1','owned_listener_port':port,'accepted_connections':len(accepted),'commands':records}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'probe_count':len(targets),'exits':[(r['label'],r['exit_code']) for r in records],
 'network':[(r['label'],r['result']) for r in records if 'network' in r['label']]}))
assert all(r['exit_code']==0 for r in records)
assert all(r['result']['public_source'] and all(not x['readable'] for x in r['result']['paths'].values()) for r in (outer,inner,worker))
