from audit import *
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.host_pins import read_registry
from tools.validation.g21_fixture import bulk
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from datetime import datetime,timezone,timedelta
import uuid
snap=json.loads((E/'05_security/db-crash-139/RECOVERED_LAST_SAVE_GRAPH.json').read_text());nodes=[decode(x[1],'tenant-g23-live') for x in snap['nodes']];edges=[decode(x[2],'tenant-g23-live') for x in snap['edges']]
r=GraphRepository.from_environment();v=r.v2(TenantBinding('tenant-g23-live',r.graph_name),read_registry(E/'03_world_accepted/private_host_pins'));v.initialize()
# Only a fresh, unserved owned target: restore exact saved state alongside actual schema constraints.
assert r.query('MATCH(n) RETURN count(n)')==[[1]]
state=[n for n in nodes if n['kind']=='TenantState'];assert len(state)==1
r.query('MATCH(s:TenantState {id:$id}) SET s=$row RETURN s.id',{'id':v.state_id,'row':native(state[0])},read_only=False)
bulk(v,[n for n in nodes if n['kind']!='TenantState'],edges)
actual=[r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id')]
assert digest(actual)==snap['sha256']
body=json.loads((E/'03_world_accepted/S1_BOOTSTRAP.json').read_text());body['binding']=v.binding.__dict__;body['grant'].update(session_id='capability-session-'+uuid.uuid4().hex,generation=uuid.uuid4().hex,authz_epoch=v.state()['authz_epoch'],valid_until=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat())
write(E/'03_world_accepted/S1_04_BOOTSTRAP.json',body);(E/'03_world_accepted/S1_04_BOOTSTRAP.json').chmod(0o600)
state,rows=resolve_v2(v,body['facts'],'query:recovered-source-check',utc_now());assert len(rows)==1 and rows[0][0]['core_verdict']=='ABSTAIN'
assert r._client.connection.save() is True
write(E/'05_security/db-crash-139/ISOLATED_LIVE_RESTORE.json',{'at':now(),'status':'PASS_EXACT_LAST_SAVE_GRAPH','source_sha256':snap['sha256'],'actual_sha256':digest(actual),'nodes':len(nodes),'edges':len(edges),'port':17752,'graph':r.graph_name,'seed_recommendation':rows[0][0],'unsaved_original_run_records':'NOT_SYNTHESIZED; preserved only in original raw tools','live_regression_instance_separation':True,'old_crashed_container':'RETAINED_STOPPED'})
print('isolated actual live graph restored from last SAVE; seed integrity verified');r.close()
