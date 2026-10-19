"""Owned runtime isolation/recovery only. No historic database/engine changes."""
from audit import *
import shutil,secrets,socket
oldcfg=json.loads((E/'RUNTIME_CONFIG.json').read_text())
image='falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62'
for role,port,memory in [('RECOVERY',17754,'5g'),('REGRESSION',17753,'5g'),('LIVE',17752,'1g')]:
 s=socket.socket();s.bind(('127.0.0.1',port));s.close()
 d=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('g23-'+role.lower()+'-1e5e8e1af0');d.mkdir(mode=0o700)
 k=d/'db.password';k.write_text(secrets.token_urlsafe(32)+'\n');k.chmod(0o600)
 c=d/'server.conf';c.write_text('bind 0.0.0.0\nprotected-mode yes\nrequirepass '+k.read_text().strip()+'\ndir /data\nsave ""\nappendonly no\n');c.chmod(0o600)
 data=E/(role.lower()+'-db-data');data.mkdir(mode=0o700)
 if role=='RECOVERY':shutil.copy2(E/'05_security/db-crash-139/dump.rdb',data/'dump.rdb')
 cfg={**oldcfg,'container':'aevora-g23-'+role.lower()+'-1e5e8e1af0','port':port,'password_file':str(k),'configuration_file':str(c),'graph':'aevora_v2_g23_live_accepted_1e5e8e1af0' if role=='RECOVERY' else 'aevora_v2_g23_live_isolated' if role=='LIVE' else 'aevora_g23_regression_isolated','resource_limit':memory,'profile':role}
 write(E/('RUNTIME_'+role+'_CONFIG.json'),cfg)
 args=['docker','run','-d','--name',cfg['container'],'--label','aevora.audit.owner='+E.name,'--label','aevora.audit.role='+role,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--publish','127.0.0.1:'+str(port)+':6379','--memory',memory,'--cpus','2','--pids-limit','256','--mount','type=bind,src='+str(c)+',dst=/run/secrets/server.conf,readonly','--mount','type=bind,src='+str(data)+',dst=/data','--entrypoint','redis-server',image,'--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no']
 assert record('new-'+role.lower()+'-db',args)==0
print('fresh profiles created; last-SAVE recovery has not yet been verified')
