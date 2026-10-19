from audit import *
import secrets,os
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());secret_dir=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('g21-perf-'+E.name[-10:]);secret_dir.mkdir(mode=0o700)
pw=secret_dir/'db.password';pw.write_text(secrets.token_urlsafe(48)+'\n');pw.chmod(0o600)
conf=secret_dir/'server.conf';conf.write_text('requirepass '+pw.read_text().strip()+'\ndir /data\nsave ""\n');conf.chmod(0o600)
(E/'perf-db-data').mkdir();name='aevora-g21-perf-'+E.name[-10:]
argv=['docker','run','-d','--name',name,'--label','aevora.audit.owner='+E.name,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--memory','1g','--cpus','2','--pids-limit','256','--publish','127.0.0.1:17732:6379','--mount',f'type=bind,src={conf},dst=/run/secrets/server.conf,readonly','--mount',f'type=bind,src={E}/perf-db-data,dst=/data','--entrypoint','redis-server','falkordb/falkordb:v4.20.4','--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no']
assert record('fresh-owned-performance-db',argv,cwd=E)==0
cfg.update(container=name,port=17732,password_file=str(pw),configuration_file=str(conf));write(E/'PERF_RUNTIME_CONFIG.json',cfg)
(E/'runtime_perf.py').write_text((E/'runtime.py').read_text().replace('RUNTIME_CONFIG.json','PERF_RUNTIME_CONFIG.json'))
