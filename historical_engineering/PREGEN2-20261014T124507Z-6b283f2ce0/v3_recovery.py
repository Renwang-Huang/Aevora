from runtime import *
import socket,uuid
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());out=E/'04_falkordb/recovery-attempt2';out.mkdir(mode=0o700);data=out/'data';data.mkdir(mode=0o700)
graph=json.loads((E/'04_falkordb/graph_controls-attempt3/RESULT.json').read_text())['graph']
capture="from aevora.graph_repository import GraphRepository;from aevora.checkpoint import capture_graph;from aevora.models import LIFECYCLE_SCHEMA_VERSION;from pathlib import Path;import json,os;r=GraphRepository(host='127.0.0.1',port=PORT,graph_name="+repr(graph)+",password=Path('/maintainer/aevora-db.password').read_text().strip());snap=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);print(json.dumps({'snapshot':snap,'server_version':r._client.connection.info('server')['redis_version'],'graph':r.graph_name,'port':PORT,'save':r._client.connection.save()}));r.close()"
assert record('v3-owned-save-capture-attempt2',runtime('-c',capture.replace('PORT','17705')))==0
assert record('v3-owned-rdb-exec-extraction',['docker','exec',cfg['container'],'cat','/data/dump.rdb'])==0
import shutil
shutil.copyfile(E/'commands/v3-owned-rdb-exec-extraction/stdout.log',data/'dump.rdb')
original=sha(data/'dump.rdb');port=17706
with socket.socket() as s:s.bind(('127.0.0.1',port))
name='aevora-pregen2-cold-'+uuid.uuid4().hex[:12]
args=['docker','run','-d','--name',name,'--label','aevora.audit.owner='+C['run_id'],'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--publish',f'127.0.0.1:{port}:6379','--memory','1g','--cpus','2','--pids-limit','256','--mount','type=bind,src='+str(data)+',dst=/data','--mount','type=bind,src='+cfg['configuration_file']+',dst=/run/secrets/server.conf,readonly','--entrypoint','redis-server','falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62','--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no']
assert record('v3-owned-cold-restore',args)==0
assert record('v3-cold-readback-before-stop',runtime('-c',capture.replace('PORT',str(port))))==0
assert record('v3-cold-normal-stop',['docker','stop','--time','15',name])==0
assert record('v3-cold-normal-start',['docker','start',name])==0
assert record('v3-cold-readback-after-start',runtime('-c',capture.replace('PORT',str(port))))==0
assert record('v3-cold-final-stop',['docker','stop','--time','15',name])==0
rows=[json.loads((E/'commands'/n/'stdout.log').read_text()) for n in ['v3-owned-save-capture-attempt2','v3-cold-readback-before-stop','v3-cold-readback-after-start']]
assert rows[0]['snapshot']==rows[1]['snapshot']==rows[2]['snapshot']
write(out/'RESULT.json',{'status':'PASS','source_container':cfg['container'],'cold_container':name,'port':port,'rdb_at_copy_sha256':original,'rdb_after_normal_stop_sha256':sha(data/'dump.rdb'),'graph':graph,'cold_restore_and_stop_start_exact_graph':True,'snapshots':[str(E/'commands'/n/'stdout.log') for n in ['v3-owned-save-capture-attempt2','v3-cold-readback-before-stop','v3-cold-readback-after-start']],'scope':'Authenticated actual RDB bytes via Docker exec, cold load,normal stop/start; NOT_AOF_OR_CRASH_TAIL_GUARANTEE','at':now()})
write(E/'04_falkordb/V3_RESULT.json',{'status':'PASS','graph_controls':15,'head_revision_false_oracle':3,'rdb_recovery':'PASS','first_collection_failures_retained':4,'AOF_RELOAD':'HISTORICAL_139_UNRESOLVED_NOT_RERUN','GLOBAL_MULTISTEP_ATOMICITY':'UNVERIFIED','model_calls':0,'at':now()})
print('V3 recovery PASS')
