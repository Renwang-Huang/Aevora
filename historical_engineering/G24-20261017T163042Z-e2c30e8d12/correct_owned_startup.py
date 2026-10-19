from audit import *
for profile in ['MODEL','REGRESSION']:
 cfg=json.loads((E/('RUNTIME_'+profile+'_CONFIG.json')).read_text());name=cfg['container']
 assert record('stop-unaccepted-'+profile,['docker','stop',name])==0
 assert record('retain-unaccepted-'+profile,['docker','rename',name,name+'-startup-unaccepted'])==0
 conf=Path(cfg['configuration_file']);raw=conf.read_text().replace('loadmodule /FalkorDB/bin/src/falkordb.so\n','');conf.write_text(raw);conf.chmod(0o600)
 cmd=['docker','run','-d','--name',name,'--label','aevora.audit.owner='+E.name,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--memory',cfg['resource_limit'],'--cpus','1','--pids-limit','256','-p',f'127.0.0.1:{cfg["port"]}:6379','--mount',f'type=bind,src={conf},dst=/run/redis.conf,readonly','--mount',f'type=bind,src={E/(profile.lower()+"-db-data")},dst=/data','--entrypoint','redis-server','falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62','--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/redis.conf']
 assert record('owned-authenticated-'+profile,cmd)==0
write(E/'00_baseline/STARTUP_FAILURE.json',dict(error='AUTHENTICATION_FAILED: image run.sh did not consume intended redis configuration',model_runs=0,solution='Explicit established redis-server entrypoint + include, fail-closed authentication checks',unaccepted_containers='Stopped, retained with -startup-unaccepted suffix',source_modified=False))
