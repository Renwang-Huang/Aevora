from audit import *
import json,time
name='aevora-g20-'+C['id'].rsplit('-',1)[-1];graph='g20_synthetic';step=0
image='falkordb/falkordb@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62'
(E/'probes/db-data').mkdir();rows=[]
def cmd(label,args,expected=0):
 code=record('probe-'+label,args);rows.append({'label':label,'exit_code':code,'expected_exit_code':expected});assert code==expected,(label,code,expected)
 return (E/'commands'/('probe-'+label)/'stdout.log').read_text()
def redis(label,*args,expected=0):return cmd(label,['docker','exec',name,'redis-cli','--json','-e',*args],expected)
def query(label,q,params=None,readonly=False,expected=0):
 text='CYPHER '+' '.join(k+'='+json.dumps(v,separators=(',',':')) for k,v in (params or {}).items())+' '+q
 out=redis(label,'GRAPH.RO_QUERY' if readonly else 'GRAPH.QUERY',graph,text,expected=expected)
 return json.loads(out) if expected==0 else out
try:
 cmd('image-identity',['docker','image','inspect',image,'--format','{{json .RepoDigests}}'])
 cmd('start',['docker','run','-d','--name',name,'--label','aevora.owner='+C['id'],'--network','none','--read-only','--memory','512m','--cpus','1','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,nodev,size=32m','--mount','type=bind,source='+str(E/'probes/db-data')+',target=/data',image,'redis-server','--loadmodule','/var/lib/falkordb/bin/falkordb.so','--appendonly','no','--save','','--dir','/data'])
 for i in range(30):
  # Startup readiness, not a business race reproduction.
  r=subprocess.run(['docker','exec',name,'redis-cli','PING'],capture_output=True)
  if r.returncode==0 and r.stdout.strip()==b'PONG':break
  time.sleep(.1)
 else:raise RuntimeError('OWNED_DB_START_FAILED')
 redis('version','INFO','server');redis('module','MODULE','LIST')
 query('init',"CREATE (:Entity {id:'one',tenant_id:'synthetic-a',payload_json:'{}',payload_sha256:'synthetic-only'})")
 query('range-index','CREATE INDEX FOR (n:Entity) ON (n.tenant_id,n.id)')
 redis('unique','GRAPH.CONSTRAINT','CREATE',graph,'UNIQUE','NODE','Entity','PROPERTIES','2','tenant_id','id')
 redis('mandatory','GRAPH.CONSTRAINT','CREATE',graph,'MANDATORY','NODE','Entity','PROPERTIES','4','id','tenant_id','payload_json','payload_sha256')
 ready=False
 for i in range(30):
  d=query('constraints-'+str(i),'CALL db.constraints()',readonly=True)
  if 'OPERATIONAL' in str(d) and str(d).count('OPERATIONAL')==2:ready=True;break
  time.sleep(.05)
 assert ready,'CONSTRAINTS_NOT_OPERATIONAL'
 query('same-id-other-tenant',"CREATE (:Entity {id:'one',tenant_id:'synthetic-b',payload_json:'{}',payload_sha256:'synthetic-only'})")
 query('duplicate-rejected',"CREATE (:Entity {id:'one',tenant_id:'synthetic-a',payload_json:'{}',payload_sha256:'synthetic-only'})",expected=1)
 query('mandatory-rejected',"CREATE (:Entity {id:'two',tenant_id:'synthetic-a'})",expected=1)
 query('fixture',"CREATE (s:TenantState {id:'state',tenant_id:'synthetic-a',epoch:0}), (m:PublicationManifest {id:'publication',tenant_id:'synthetic-a',epoch:1}), (e:Experience {id:'experience',tenant_id:'synthetic-a'}), (r:ExperienceRevision {id:'revision',tenant_id:'synthetic-a'}), (e)-[:HAS_REVISION]->(r), (r)-[:PUBLISHED_BY]->(m), (c:Context {id:'context',tenant_id:'synthetic-a'}), (a:Authority {id:'authority',tenant_id:'synthetic-a',kind:'INDEPENDENT_ORACLE'}) WITH s,m,e,r,c,a UNWIND ['PASS','FAIL'] AS verdict CREATE (ev:Evidence {id:'evidence-'+verdict,tenant_id:'synthetic-a'}), (o:VerifiedOutcome {id:'outcome-'+verdict,tenant_id:'synthetic-a',verdict:verdict}), (ev)-[:VERIFIES]->(o), (o)-[:IN_CONTEXT]->(c), (o)-[:ATTESTED_BY]->(a)")
 query('positive-edge',"MATCH (r:ExperienceRevision {id:'revision'}),(ev:Evidence {id:'evidence-PASS'}) CREATE (r)-[:SUPPORTED_BY {id:'support-edge'}]->(ev)")
 query('counter-edge',"MATCH (r:ExperienceRevision {id:'revision'}),(ev:Evidence {id:'evidence-FAIL'}) CREATE (r)-[:COUNTEREXAMPLE {id:'counter-edge'}]->(ev)")
 params={'state':'state','tenant':'synthetic-a','manifest':'publication','expected':0,'next':1,'edge':'commit-edge'}
 fence=(P/'docs/gen2/g20/cypher/Q07_epoch_fence_probe.cypher').read_text()
 accepted=query('fence-first',fence,params);stale=query('fence-stale',fence,params)
 assert accepted[1]==[[1,'publication']] and stale[1]==[],(accepted,stale)
 paths=(P/'docs/gen2/g20/cypher/Q04_evidence_paths.cypher').read_text();p={'state':'state','tenant':'synthetic-a','experience':'experience'}
 before=query('paths-complete',paths,p,readonly=True);assert len(before[1])==2
 cross=query('paths-cross-tenant',paths,{**p,'tenant':'synthetic-b'},readonly=True);assert cross[1]==[]
 query('cut-owned-support',"MATCH (:ExperienceRevision {id:'revision'})-[x:SUPPORTED_BY]->() DELETE x")
 cut=query('paths-cut',paths,p,readonly=True);assert len(cut[1])==1 and cut[1][0][1]=='COUNTEREXAMPLE'
 query('restore-owned-support',"MATCH (r:ExperienceRevision {id:'revision'}),(ev:Evidence {id:'evidence-PASS'}) CREATE (r)-[:SUPPORTED_BY {id:'support-edge'}]->(ev)")
 restored=query('paths-restored',paths,p,readonly=True);assert restored[1]==before[1]
 redis('query-plan','GRAPH.EXPLAIN',graph,'CYPHER tenant="synthetic-a" state="state" experience="experience" '+paths)
 write(E/'probes/RESULT.json',{'status':'PASS_SYNTHETIC_QUERY_AND_CONSTRAINT_SHAPES_ONLY','at':now(),'source':'REAL_OWNED_FALKORDB_NO_NETWORK','image':image,'constraint_ready':True,'duplicate_actual_exit':1,'mandatory_actual_exit':1,'same_id_other_tenant_allowed':True,'fenced_first_rows':accepted[1],'fenced_stale_rows':stale[1],'multi_hop_rows':2,'cut_rows':1,'restored_rows':2,'cross_tenant_rows':0,'actual_core_arbitrator':'NOT_IMPLEMENTED_NOT_EXECUTED','agent_or_oracle_outcomes':'NOT_CREATED','production_atomic_lifecycle':'NOT_RUN','raw_commands':rows})
finally:
 if subprocess.run(['docker','container','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
  owned=subprocess.check_output(['docker','inspect',name,'--format','{{index .Config.Labels "aevora.owner"}}'],text=True).strip();assert owned==C['id']
  cmd('stop',['docker','stop','--time','10',name]);cmd('remove',['docker','rm',name])
 write(E/'probes/OWNED_RESOURCE_CLOSURE.json',{'at':now(),'container':name,'stopped_and_removed':True,'data_retained':str(E/'probes/db-data'),'historical_volumes_accessed':False,'published_ports':[],'network':'none'})
print('SYNTHETIC_DESIGN_PROBE_COMPLETE')
