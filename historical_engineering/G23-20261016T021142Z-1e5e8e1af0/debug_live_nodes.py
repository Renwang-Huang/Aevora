from audit import *
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
r=GraphRepository.from_environment();v=r.v2(TenantBinding('tenant-g23-live',r.graph_name),__import__('aevora.host_pins',fromlist=['read_registry']).read_registry(E/'03_world_accepted/private_host_pins'));print(json.dumps([v.node(x[0]) for x in r.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id',{'run':'ffa24f85-7915-4e4a-8add-008f7dffd13c'})],indent=2));r.close()
