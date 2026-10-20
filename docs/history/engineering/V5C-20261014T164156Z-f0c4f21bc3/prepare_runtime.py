from audit import *
import secrets, socket, uuid
cfg=json.loads((E/'RUNTIME_PRECONFIG.json').read_text())
probe=socket.socket();probe.bind(('127.0.0.1',cfg['port']));probe.close()
private=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('v5c-'+uuid.uuid4().hex);private.mkdir(mode=0o700)
key=private/'falkordb.password';key.write_text(secrets.token_urlsafe(32)+'\n');key.chmod(0o600)
conf=private/'falkordb.conf';conf.write_text('bind 0.0.0.0\nprotected-mode yes\nport 6379\nrequirepass '+key.read_text().strip()+'\ndir /data\ndbfilename dump.rdb\nsave ""\nappendonly no\n');conf.chmod(0o600)
cfg.update(password_file=str(key),configuration_file=str(conf));write(E/'RUNTIME_CONFIG.json',cfg)
data=E/'owned_db_data';data.mkdir(mode=0o700)
image='falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62'
args=['docker','run','-d','--name',cfg['container'],'--label','aevora.audit.owner='+E.name,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--publish','127.0.0.1:'+str(cfg['port'])+':6379','--memory','1g','--cpus','2','--pids-limit','256','--mount','type=bind,src='+str(conf)+',dst=/run/secrets/server.conf,readonly','--mount','type=bind,src='+str(key)+',dst=/run/secrets/db.password,readonly','--mount','type=bind,src='+str(data)+',dst=/data','--entrypoint','redis-server',image,'--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no']
assert record('c0-owned-db-start',args)==0
write(E/'00_environment/SECRETS_METADATA.json',{'external_secret_directory':str(private),'directory_mode':oct(private.stat().st_mode&0o777),'password_file_mode':oct(key.stat().st_mode&0o777),'credential_values':'NOT_ARCHIVED','individual_secret_sha256':'NOT_COMPUTED','api_secret_source':'Existing trusted Host project credential; not mounted in Participant'})
from runtime import runtime
assert record('c0-install',runtime('-m','pip','install','-e',E/'owned_runtime/source/aevora_core','-e',E/'owned_runtime/source/console','-e',E/'owned_runtime/source','setuptools==76.1.0','wheel==0.45.1'))==0
assert record('c0-pip-check',runtime('-m','pip','check'))==0
assert record('c0-package-inventory',runtime('-m','pip','list','--format=json'))==0
assert record('c0-dev-help',runtime('tools/dev.py','--help'))==0
assert record('c0-owned-db-state',['docker','inspect','--format','{{json .State}}',cfg['container']])==0
print('OWNED_RUNTIME_READY',flush=True)
