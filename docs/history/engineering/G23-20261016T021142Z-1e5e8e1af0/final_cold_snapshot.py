"""Final owned live snapshot/SAVE; reads actual current state, no invented outcome."""
from audit import *
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
from aevora.host_pins import read_registry
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
import sys
label=sys.argv[1];out=E/'06_cold_recovery';out.mkdir(exist_ok=True)
r=GraphRepository.from_environment();assert r.graph_name=='aevora_v2_g23_live_isolated';v=r.v2(TenantBinding('tenant-g23-live',r.graph_name),read_registry(E/'03_world_accepted/private_host_pins'));nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id');edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id');facts=json.loads((E/'04_live/S1_05/HOST_PUBLICATION.json').read_text())['review']['facts'];state,recs=resolve_v2(v,facts,'query:final-cold-observation',utc_now());assert any(x[0]['experience_id']=='Experience:fff362bc8232ff84f561067ee5c6ea7266f2947e26fab8df6e2685e115f99ccc' and x[0]['core_verdict']=='APPLY' for x in recs)
body=dict(status='PASS_CURRENT_GRAPH_INTEGRITY',nodes=nodes,edges=edges,sha256=digest([nodes,edges]),state=state,recommendations=recs,at=now());write(out/(label+'.json'),body)
if label=='before':assert r._client.connection.save() is True
else:
 before=json.loads((out/'before.json').read_text());assert before['sha256']==body['sha256'] and before['state']==state
 write(out/'RESULT.json',dict(status='PASS_EXPLICIT_SAVE_GRACEFUL_RESTART_EXACT_GRAPH',before_sha256=before['sha256'],after_sha256=body['sha256'],nodes=len(nodes),edges=len(edges),at=now(),unsaved_tail_and_power_loss='UNVERIFIED'))
r.close();print(label,body['sha256'])
