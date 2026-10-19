#!/usr/bin/env python3
"""Rebuild a pinned Aevora/OrderFlow source commit using fresh official tooling.

Maintainer only. No cached interpreter/venv/container/database is copied. A real
isolated authenticated FalkorDB endpoint is an explicit prerequisite; supplied
credentials stay in their host-only file and are never archived or printed.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.aevora_h2_junit import check_junit

def digest(p):return sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):
 with p.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source-repository',type=Path,required=True);p.add_argument('--source-commit',required=True)
 p.add_argument('--destination',type=Path,required=True);p.add_argument('--evidence-directory',type=Path,required=True)
 p.add_argument('--database-port',type=int,required=True);p.add_argument('--graph',required=True)
 p.add_argument('--password-file',type=Path,required=True)
 p.add_argument('--runtime-root',type=Path,required=True,help='Freshly downloaded approved /usr runtime, with Python3.12 and pidfd_open')
 p.add_argument('--baseline-identities',type=Path,required=True)
 p.add_argument('--cgroup-parent',type=Path,required=True)
 p.add_argument('--recorded-graph-maintenance',action='store_true',
  help='Use the H2-only recorded SAVE pause/restoration window for unchanged graph-copy tests')
 a=p.parse_args();dest=a.destination.absolute();evidence=a.evidence_directory.absolute()
 if dest.exists() or evidence.exists():raise ValueError('Fresh exclusive destination/evidence directory required')
 if a.database_port==16379 or a.graph.startswith('aevora_h1'):raise ValueError('Use an isolated H2 endpoint')
 if len(a.source_commit)!=40 or any(c not in '0123456789abcdef' for c in a.source_commit):raise ValueError('Full approved source commit required')
 uv=shutil.which('uv');git=shutil.which('git')
 if not uv or not git:raise ValueError('Explicit uv/git host prerequisites required')
 secret=a.password_file.absolute()
 if not secret.is_file() or secret.is_symlink():raise ValueError('Owned private credential file required')
 st=secret.stat()
 if st.st_uid!=os.getuid() or st.st_nlink!=1 or st.st_mode&0o077:raise ValueError('Credential ownership/mode invalid')
 evidence.mkdir(parents=True);dest.parent.mkdir(parents=True,exist_ok=True)
 env={'PATH':'/usr/bin:/bin','HOME':str(evidence/'empty-home'),'LANG':'C.UTF-8'}
 Path(env['HOME']).mkdir()
 env.update({'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null','GIT_CONFIG_NOSYSTEM':'1',
  'AEVORA_FALKORDB_HOST':'127.0.0.1','AEVORA_FALKORDB_PORT':str(a.database_port),'AEVORA_FALKORDB_GRAPH':a.graph,
  'AEVORA_FALKORDB_PASSWORD_FILE':str(secret),'ORDERFLOW_CGROUP_PARENT':str(a.cgroup_parent),'PYTHONNOUSERSITE':'1'})
 receipts=[]
 def run(label,argv,cwd):
  d=evidence/label;d.mkdir();started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
  with (d/'stdout.log').open('wb') as out,(d/'stderr.log').open('wb') as err:
   r=subprocess.run(argv,cwd=cwd,env=env,stdout=out,stderr=err)
  v={'argv':list(map(str,argv)),'cwd':str(cwd),'started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),
   'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-clock,'stdout_sha256':digest(d/'stdout.log'),'stderr_sha256':digest(d/'stderr.log')}
  write(d/'command.json',v);receipts.append(v)
  if r.returncode:raise RuntimeError('Rebuild stage failed: '+label+'; inspect retained original receipt/logs')
 run('clone',[git,'clone','--no-hardlinks',str(a.source_repository.absolute()),str(dest)],dest.parent)
 run('checkout',[git,'checkout','--detach',a.source_commit],dest)
 actual=subprocess.check_output([git,'rev-parse','HEAD'],cwd=dest,env=env,text=True).strip();assert actual==a.source_commit
 runtime=a.runtime_root.resolve(strict=True)
 if not (runtime/'bin/python3.12').is_file():raise ValueError('Approved runtime layout is required')
 bwrap=shutil.which('bwrap')
 if not bwrap:raise ValueError('bubblewrap required; no unsandboxed fallback')
 def trusted(argv):
  # Maintainer rebuild only. Candidate and Participant retain their independent
  # narrower sandboxes; neither receives this credential or checkout mount.
  return [bwrap,'--die-with-parent','--unshare-user','--unshare-pid',
   '--ro-bind',str(runtime),'/usr','--ro-bind',bwrap,'/tools/bwrap',
   '--ro-bind',git,'/tools/git','--ro-bind',uv,'/tools/uv',
   '--ro-bind','/etc/resolv.conf','/etc/resolv.conf',
   '--ro-bind','/etc/ssl/certs','/etc/ssl/certs',
   '--ro-bind',str(secret),'/maintainer/db.password',
   '--bind','/sys/fs/cgroup','/sys/fs/cgroup',
   '--symlink','usr/bin','/bin',
   '--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
   '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
   '--bind',str(dest),str(dest),'--bind',str(evidence),str(evidence),
   '--chdir',str(dest),'--clearenv',
   '--setenv','HOME','/tmp','--setenv','PATH','/tools:/usr/bin:/bin',
   '--setenv','SSL_CERT_FILE','/etc/ssl/certs/ca-certificates.crt',
   '--setenv','PYTHONNOUSERSITE','1',
   '--setenv','AEVORA_FALKORDB_HOST','127.0.0.1',
   '--setenv','AEVORA_FALKORDB_PORT',str(a.database_port),
   '--setenv','AEVORA_FALKORDB_GRAPH',a.graph,
   '--setenv','AEVORA_FALKORDB_PASSWORD_FILE','/maintainer/db.password',
   '--setenv','ORDERFLOW_CGROUP_PARENT',str(a.cgroup_parent),*argv]
 run('runtime-capabilities',trusted(['/usr/bin/python3.12','-c',
  "import os,sys,sqlite3,json;assert sys.version_info[:2]==(3,12);assert hasattr(os,'pidfd_open');print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version,'pidfd_open':True}))"]),dest)
 run('venv-create',trusted(['/tools/uv','venv',str(dest/'.venv'),'--python','/usr/bin/python3.12','--no-config','--no-project','--no-cache']),dest)
 python=dest/'.venv/bin/python'
 lock=dest/'aevora_core/requirements.lock.txt'
 run('dependencies',trusted(['/tools/uv','pip','install','--python',str(python),'-r',str(lock),'--no-config','--no-cache','--default-index','https://pypi.org/simple','--strict']),dest)
 run('packages',trusted(['/tools/uv','pip','install','--python',str(python),'-e',str(dest),'-e',str(dest/'aevora_core'),'--no-config','--no-cache','--default-index','https://pypi.org/simple','--strict']),dest)
 code="import json,sys,sqlite3,importlib.metadata as m;from aevora.graph_repository import GraphRepository;r=GraphRepository.from_environment();s=r.initialize();state=r.state_fingerprint();p=r.snapshot_public_paths('experience:sqlite-atomic-reservation');print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version,'packages':{x:m.version(x) for x in ['aevora-core','orderflow-incident-lab','FalkorDB','redis','mcp','pytest']},'schema':s,'graph_state':state,'real_public_multihop_paths':p}));r.close()"
 run('real-graph-query',trusted([str(python),'-c',code]),dest)
 # Sanitized PYTHONPATH plus a fresh non-system-site venv retains the checkout's
 # namespace scripts package, which is intentionally not an installed package.
 if a.recorded_graph_maintenance:
  if a.database_port!=17679:raise ValueError('Recorded maintenance is confined to the explicit H2 endpoint')
  regression_output=evidence/'recorded-regression'
  run('regression',trusted([str(python),'-m','scripts.aevora_h2_governance','--pause-auto-save','tests',str(regression_output),'-q','tests','aevora_core/tests']),dest)
  junit_path=regression_output/'JUNIT.xml'
 else:
  run('regression',trusted([str(python),'-m','pytest','-q','tests','aevora_core/tests','--junitxml='+str(evidence/'REBUILD_JUNIT.xml')]),dest)
  junit_path=evidence/'REBUILD_JUNIT.xml'
 junit=check_junit(junit_path,json.loads(a.baseline_identities.read_text())['identities'])
 write(evidence/'JUNIT_IDENTITY_GATE.json',junit)
 if junit['status']!='PASS':raise ValueError('Inherited identity/JUnit gate failed')
 modified=subprocess.check_output([git,'diff','--name-only',a.source_commit],cwd=dest,env=env,text=True).splitlines()
 if modified:raise ValueError('Rebuild modified tracked source: '+str(modified))
 write(evidence/'REBUILD_RESULT.json',{'status':'PASS','source_commit':actual,'clean_source':str(dest),'interpreter':'/usr/bin/python3.12','runtime_root':str(runtime),'interpreter_binary_sha256':digest(runtime/'bin/python3.12'),'dependency_lock_sha256':digest(lock),'baseline_identities_sha256':digest(a.baseline_identities),'stage_count':len(receipts),'actual_regression_exit':receipts[-1]['exit_code'],'junit':junit,'personal_venv_or_pip_cache_reused':False,'runtime_download_authority':'External independently archived runtime acquisition receipts; this entry checks capabilities, not origin','model_calls':0,'secrets_archived':False,'scope':'Explicit Linux/kernel/cgroup/docker/uv/git/runtime prerequisites; public network installs and authenticated isolated FalkorDB'})
 print(json.dumps({'status':'PASS','commit':actual,'evidence':str(evidence),'stages':len(receipts)}))
if __name__=='__main__':main()
