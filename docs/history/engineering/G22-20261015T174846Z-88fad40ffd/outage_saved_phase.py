"""Actual owned DB outage and RDB-restart recovery, no historical volume access."""
from pathlib import Path
import sys,json,time,hashlib,gzip
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.orderflow_outcome_bridge import TrustAnchor
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from aevora_maintainer.host_v2 import TrustedHost,HostGrant,Prepared
from tools.validation.g22_fixture import admitted
E=Path(__file__).parent;O=E/'04_security/outage-recovery-saved';O.mkdir(exist_ok=True)
phase=sys.argv[1];raw=gzip.open(O/('RAW_'+phase+'.jsonl.gz'),'xt',compresslevel=3);original=GraphRepository.query

def query(self,statement,params=None,*,read_only=True):
 rows=[];error=None;t=time.monotonic()
 try:rows=original(self,statement,params,read_only=read_only);return rows
 except Exception as ex:error=type(ex).__name__;raise
 finally:raw.write(canonical_json(dict(statement=statement,params=params,rows=rows,error=error,seconds=time.monotonic()-t))+'\n');raw.flush()
GraphRepository.query=query
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_outage_saved')
v=r.v2(TenantBinding('tenant-g22-outage',r.graph_name),TrustRegistry());v.initialize()
cases=json.loads((E/'01_admission/final-cases/CASES.json').read_text());case=cases['cases'][0]
a=TrustAnchor(Path(case['root']),case['manifest_sha256'],{'evaluation_report.json':case['run_id']},profile='current_live',manifest_relative_path='HOST_RUN_MANIFEST.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],source_manifest_relative_path='SOURCE_MANIFEST.json')
if phase=='prepare':grant=TrustedHost.bootstrap(v,O/'private_host_pins',principal='outage-maintainer',allowed_scope={'task.shared_state_kind':['sqlite_file']})
else:grant=HostGrant(**json.loads((O/'METADATA.json').read_text())['grant'])
h=TrustedHost(v,O/'private_host_pins',grant);h.case=case;h.verifier=h.register_orderflow(a,case['evaluator_sha'],case['suite_sha'])
def snapshot(name):
 nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id');edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id')
 value=dict(nodes=nodes,edges=edges,sha256=digest([nodes,edges]));(O/name).write_text(json.dumps(value,sort_keys=True));return value['sha256']
if phase=='prepare':
 c,s,out,review=admitted(h,'actual-outage');head=h.transition(c['id'],'PUBLISHING',expected_head=digest(h.head(c['id'])),reason='Prepare during actual controlled DB outage')
 (O/'METADATA.json').write_text(json.dumps(dict(grant=grant.__dict__,candidate_id=c['id'],review_id=review['id']),indent=2))
 put=v.put_document
 def interrupted(kind,*args,**kwargs):
  if kind=='PublicationManifest':
   assert r._client.connection.save() is True
   (O/'SAVE_BEFORE_OUTAGE.json').write_text(json.dumps(dict(actual_save=True,at=utc_now(),scope='all staged bytes before manifest write; no publication')))
   (O/'WAIT_FOR_DB_STOP.json').write_text(json.dumps(dict(epoch=v.state()['epoch'],commits=r.query('MATCH(:TenantState)-[c:COMMITS]->() RETURN count(c)')[0][0],at=utc_now())))
   deadline=time.monotonic()+60
   while not (O/'DB_STOPPED_GO').exists():
    if time.monotonic()>deadline:raise TimeoutError('Parent failed to stop owned DB within safety window')
    time.sleep(.02)
  return put(kind,*args,**kwargs)
 v.put_document=interrupted
 try:
  h.prepare(c['id'],review['id'],request_key='interrupted',expected_head=digest(head),expected_epoch=0)
  raise AssertionError('Preparation unexpectedly survived actual DB outage')
 except Exception as error:
  assert type(error).__name__ in {'GraphUnavailable','V2Error'},type(error).__name__
  (O/'OUTAGE_OBSERVED.json').write_text(json.dumps(dict(status='EXPECTED_DB_FAILURE_OBSERVED',error=type(error).__name__,code=getattr(error,'code',None),at=utc_now())))
elif phase=='recover':
 meta=json.loads((O/'METADATA.json').read_text());assert v.state()['epoch']==0 and v.discover({},v.state())==[]
 prep=h.prepare(meta['candidate_id'],meta['review_id'],request_key='recover-after-outage',expected_head=digest(h.head(meta['candidate_id'])),expected_epoch=0)
 receipt=h.publish(prep);assert v.state()['epoch']==1
 before=snapshot('BEFORE_COLD_RESTART.json')
 result=dict(prepared=prep.__dict__,receipt=receipt,graph_sha256=before,save=r._client.connection.save())
 (O/'RECOVERED.json').write_text(json.dumps(result,indent=2))
elif phase=='verify':
 expected=json.loads((O/'RECOVERED.json').read_text());assert snapshot('AFTER_COLD_RESTART.json')==expected['graph_sha256']
 receipt=h.publish(Prepared(**expected['prepared']));assert receipt==expected['receipt'] and v.state()['epoch']==1
 assert r.query('MATCH(:TenantState)-[c:COMMITS]->() RETURN count(c)')==[[1]]
 review=v.node(json.loads((O/'METADATA.json').read_text())['review_id'])
 assert resolve_v2(v,review['facts'],'query:rdb-recovered',utc_now())[1][0][0]['core_verdict']=='APPLY'
 (O/'COLD_RECOVERY_RESULT.json').write_text(json.dumps(dict(status='PASS_RDB_LAST_SAVE_ONLY',graph_sha256=expected['graph_sha256'],receipt_id=receipt['id'],epoch=1,duplicate_commits=0,unsaved_power_loss='UNVERIFIED',aof139='KNOWN_LIMITATION')))
else:raise ValueError('Unknown controlled phase')
raw.close();r.close();print(phase,'complete')
