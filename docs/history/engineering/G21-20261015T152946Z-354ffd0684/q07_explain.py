"""Engine EXPLAIN only. NOT a production publication, source verification or CAS test."""
from pathlib import Path
import re,json,hashlib,os
from aevora.graph_repository import GraphRepository
from aevora.models import digest
E=Path(__file__).resolve().parent
os.environ['AEVORA_FALKORDB_GRAPH']='aevora_v2_g21_proof_support'
r=GraphRepository.from_environment();p=E/'worktree/docs/gen2/g21/cypher/Q07_prepared_publication_fence.cypher';text=p.read_text();params={v:'EXPLAIN_ONLY' for v in set(re.findall(r'\$([A-Za-z_][A-Za-z0-9_]*)',text))}
for k in ['expected_epoch','expected_authz_epoch','next_epoch','next_sequence']:params[k]=1
params['prepared_chunk_pins']=[]
def snapshot():return [r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),r.query('MATCH(a)-[r]->(b) RETURN a.id,type(r),properties(r),b.id ORDER BY r.id')]
before=digest(snapshot());plan=str(r._graph.explain(text,params));after=digest(snapshot());assert before==after
out=dict(status='PASS_ENGINE_EXPLAIN_ONLY',query_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),params=params,plan=plan,before_sha256=before,after_sha256=after,production_publication='NOT_IMPLEMENTED_NOT_RUN',concurrent_CAS='NOT_RUN')
(E/'reports/Q07_ENGINE_EXPLAIN.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));r.close()
