from runtime import *
import socket,uuid
os.umask(0o077)
assert record('v0-owned-source-clone',['git','-c','gc.auto=0','clone','--no-local','--branch','aevora-gen2-baseline',W,P])==0
prior=json.loads((E/'00_environment/repo_integrity.json').read_text())['source547_sha256'];assert {n:sha(P/n) for n in prior}==prior
old=json.loads((G5/'RUNTIME_CONFIG.json').read_text())
assert record('v0-owned-toolchain-copy',['rsync','-aHAX','--numeric-ids',old['runtime']+'/',str(E/'owned_runtime/usr')+'/'])==0
secret=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('pregen2-'+uuid.uuid4().hex)
assert record('v0-external-secret',['python3',str(P/'scripts/aevora_bootstrap.py'),str(secret)])==0
port=17705;s=socket.socket();s.bind(('127.0.0.1',port));s.close()
name='aevora-pregen2-'+C['run_id'].split('-')[-1]
cfg={'runtime':str(E/'owned_runtime/usr'),'venv':str(E/'owned_runtime/venv'),'password_file':str(secret/'falkordb.password'),'configuration_file':str(secret/'falkordb.conf'),'port':port,'graph':'aevora_pregen2_legacy','container':name,'cgroup':'/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.gnome.Terminal.slice','participant_boundary':'NOT_THIS_DRIVER; participant_sandbox.py only'}
write(E/'RUNTIME_CONFIG.json',cfg)
argv=['docker','run','-d','--name',name,'--label','aevora.audit.owner='+C['run_id'],'--read-only','--tmpfs','/data:rw,nosuid,nodev,size=512m','--tmpfs','/tmp:rw,nosuid,nodev','--publish',f'127.0.0.1:{port}:6379','--memory','1g','--cpus','2','--pids-limit','256','--mount','type=bind,src='+cfg['configuration_file']+',dst=/run/secrets/server.conf,readonly','--mount','type=bind,src='+cfg['password_file']+',dst=/run/secrets/db.password,readonly','--entrypoint','redis-server','falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62','--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no']
assert record('v0-owned-db',argv)==0
assert record('v0-venv',runtime('-m','venv',cfg['venv'],base=True))==0
assert record('v0-install',runtime('-m','pip','install','-e',str(P/'aevora_core'),'-e',str(P/'console'),'-e',P,'setuptools==76.1.0','wheel==0.45.1'))==0
assert record('v0-pip-check',runtime('-m','pip','check'))==0
assert record('v0-runtime-versions',runtime('-c',"import sys,sqlite3,json,importlib.metadata as m;print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version,'packages':{x:m.version(x) for x in ['pytest','mcp','falkordb','redis','aevora-core','aevora-console']}}))"))==0
assert record('v0-isolation-mapping',runtime('-c',"from pathlib import Path;import os,errno,json;assert not Path("+repr(str(W))+ ").exists();p=Path("+repr(str(RA/'evaluator/hidden_tests/episode_a/conftest.py'))+");assert p.is_file();d=p.read_bytes();ok=False\ntry:f=os.open(p,os.O_WRONLY)\nexcept OSError as e:assert e.errno in [errno.EROFS,errno.EACCES];ok=True\nelse:os.close(f)\nassert ok;print(json.dumps({'status':'PASS','frozen_source_not_mounted':True,'history_readonly':True,'HISTORY_DEPENDENCY':'YES'}))",history=True))==0
print('SETUP_PASS',flush=True)
