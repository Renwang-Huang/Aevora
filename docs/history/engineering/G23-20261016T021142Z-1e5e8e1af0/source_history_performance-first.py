from audit import *
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from tools.validation.g21_fixture import bulk
old=E.parent/'G22-20261015T174846Z-88fad40ffd'
out=E/'05_performance';out.mkdir(exist_ok=True)
data=json.loads((old/'00_baseline/performance-before.json').read_text())
registry=json.loads((old/'00_baseline/performance-unprofiled/registry.json').read_text());fs=json.loads((old/'00_baseline/performance-unprofiled/facts.json').read_text())
r=GraphRepository.from_environment();v=r.v2(TenantBinding('tenant-g21-proof',r.graph_name),TrustRegistry(**registry));v.initialize()
bulk(v,[decode(x[1],v.tenant) for x in data['nodes']],[decode(x[2],v.tenant) for x in data['edges']])
write(out/'FIXTURE_RECEIPT.json',{'origin':'G22 fixed HOST_CONTROLLED_SYNTHETIC_64x8; not new Agent/Outcome','source_sha256':sha(old/'00_baseline/performance-before.json'),'nodes':len(data['nodes']),'edges':len(data['edges']),'current_graph':r.graph_name,'port':os.environ['AEVORA_FALKORDB_PORT']})
write(out/'registry.json',registry);write(out/'facts.json',fs);r.close()
