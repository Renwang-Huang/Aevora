from audit import *
from runtime import runtime
import shutil,socket,secrets
old=E.parent/'G22-20261015T174846Z-88fad40ffd'; cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());s=socket.socket();s.bind(('127.0.0.1',cfg['port']));s.close()
private=Path(cfg['password_file']).parent;private.mkdir(mode=0o700)
k=Path(cfg['password_file']);k.write_text(secrets.token_urlsafe(32)+'\n');k.chmod(0o600)
c=Path(cfg['configuration_file']);c.write_text('bind 0.0.0.0\nprotected-mode yes\nrequirepass '+k.read_text().strip()+'\ndir /data\nsave ""\nappendonly no\n');c.chmod(0o600)
shutil.copytree(old/'venv',E/'venv',symlinks=True)
shutil.copytree(E.parent/'V5C1-20261015T054437Z-fb77b23eff/owned_runtime/native',E/'owned_runtime/native',symlinks=True)
(E/'db-data').mkdir(mode=0o700)
args=['docker','run','-d','--name',cfg['container'],'--label','aevora.audit.owner='+E.name,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--publish','127.0.0.1:'+str(cfg['port'])+':6379','--memory','3g','--cpus','2','--pids-limit','256','--mount','type=bind,src='+str(c)+',dst=/run/secrets/server.conf,readonly','--mount','type=bind,src='+str(E/'db-data')+',dst=/data','--entrypoint','redis-server','falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62','--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no']
assert record('owned-db-start',args)==0
assert record('editable-install',runtime('-m','pip','install','--no-index','--no-deps','--no-build-isolation','-e',P,'-e',P/'aevora_core','-e',P/'console'))==0
for label,args in [('pip-check',('-m','pip','check')),('dev-help',('tools/dev.py','--help')),('imports',('-I','-B','-c','import evaluator,benchmark,aevora;print(evaluator.__file__,benchmark.__file__,aevora.__file__)')),('versions',('-c','import sys,sqlite3;print(sys.version);print(sqlite3.sqlite_version)'))]:assert record(label,runtime(*args))==0
assert record('native-version',runtime('-c','import subprocess,os;raise SystemExit(subprocess.call([os.environ["ORDERFLOW_CODEX_BINARY"],"--version"]))',native=True))==0
assert record('native-help',runtime('-c','import subprocess,os;raise SystemExit(subprocess.call([os.environ["ORDERFLOW_CODEX_BINARY"],"exec","--help"]))',native=True))==0
assert record('native-features',runtime('-c','import subprocess,os;raise SystemExit(subprocess.call([os.environ["ORDERFLOW_CODEX_BINARY"],"features","list"]))',native=True))==0
for label,args,cwd in [('new-head',['git','--no-optional-locks','rev-parse','HEAD','HEAD^{tree}'],P),('new-fsck',['git','--git-dir='+str(E/'repository.git'),'fsck','--full'],E),('old-clean',['git','--no-optional-locks','status','--short','--branch'],old/'worktree'),('frozen-main',['git','--no-optional-locks','status','--short','--branch'],Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/aevora'))]:assert record(label,args,cwd=cwd)==0
write(E/'00_baseline/SETUP_RESULT.json',{'status':'PASS','upstream_request_cap':None,'shared_kernel_isolation':'PARTIAL','new_owned_db':cfg['container'],'old_database_touched':False})
