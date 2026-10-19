"""Fresh G24 services; never changes retained previous deployments."""
from audit import *
import secrets, shutil, socket
from runtime import runtime
old=E.parent/'G23-20261016T021142Z-1e5e8e1af0'
private=Path('/home/PRIVATE_MAINTAINER/.config/aevora/g24-83700e0a59')
private.mkdir(mode=0o700,exist_ok=False)
shutil.copytree(old/'venv',E/'venv',symlinks=True)
shutil.copytree(old/'owned_runtime/native',E/'owned_runtime/native',symlinks=True)
image='falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62'
for profile,port,memory in [('MODEL',17962,'1g'),('REGRESSION',17963,'5g'),('RELIABILITY',17964,'2g')]:
    with socket.socket() as s:s.bind(('127.0.0.1',port))
    key=private/(profile.lower()+'.password');key.write_text(secrets.token_urlsafe(32)+'\n');key.chmod(0o600)
    conf=private/(profile.lower()+'.conf')
    conf.write_text('bind 0.0.0.0\nprotected-mode yes\nrequirepass '+key.read_text().strip()+'\ndir /data\nsave ""\nappendonly no\n')
    conf.chmod(0o600)
    data=E/(profile.lower()+'-db-data');data.mkdir(mode=0o700)
    cfg=dict(profile=profile,container='aevora-g24-83700e0a59-'+profile.lower(),port=port,password_file=str(key),configuration_file=str(conf),graph='aevora_g24_'+profile.lower(),resource_limit=memory,runtime=json.loads((old/'RUNTIME_LIVE_CONFIG.json').read_text())['runtime'],venv=str(E/'venv'),cgroup=json.loads((old/'RUNTIME_LIVE_CONFIG.json').read_text())['cgroup'],image=image)
    write(E/('RUNTIME_'+profile+'_CONFIG.json'),cfg)
    args=['docker','run','-d','--name',cfg['container'],'--label','aevora.audit.owner='+E.name,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--memory',memory,'--cpus','2','--pids-limit','256','-p',f'127.0.0.1:{port}:6379','--mount',f'type=bind,src={conf},dst=/run/redis.conf,readonly','--mount',f'type=bind,src={data},dst=/data','--entrypoint','redis-server',image,'--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/redis.conf']
    assert record('owned-db-start-'+profile,args)==0
assert record('editable-install',runtime('-m','pip','install','--no-index','--no-deps','--no-build-isolation','-e',P,'-e',P/'aevora_core','-e',P/'console'))==0
for label,args in [('dev-help',('tools/dev.py','--help')),('runner-help',('-m','benchmark.h2_cli','run-codex','--help')),('pip-check',('-m','pip','check')),('runtime-versions',('-c','import sys,sqlite3,importlib.metadata as m;print(sys.version);print(sqlite3.sqlite_version);print({k:m.version(k) for k in ["falkordb","redis","pytest","mcp","aevora-core"]})'))]:
    assert record(label,runtime(*args))==0
for label,args in [('native-version',['--version']),('native-exec-help',['exec','--help']),('native-features',['features','list'])]:
    code='import subprocess,os;raise SystemExit(subprocess.call([os.environ["ORDERFLOW_CODEX_BINARY"],*'+repr(args)+']))'
    assert record(label,runtime('-c',code,native=True))==0
for label,args in [('baseline-head',['git','show','--no-patch','--format=fuller','HEAD']),('baseline-tree',['git','rev-parse','HEAD','HEAD^{tree}']),('runtime-ancestor',['git','merge-base','--is-ancestor','8e148f0852a961ca9f2e81bbdb5b9cb69022f450','HEAD']),('runtime-final-diff',['git','diff','8e148f0852a961ca9f2e81bbdb5b9cb69022f450','HEAD']),('baseline-clean',['git','--no-optional-locks','status','--short','--branch'])]:
    assert record(label,args)==0
write(E/'00_baseline/SETUP_RESULT.json',dict(status='PASS',model_requests=0,financial_cap=None,token_cap=None,request_cap=None,native_wall_timeout=None,previous_canceled_attempt_untouched=True))
