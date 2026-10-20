from pathlib import Path
import json,uuid
from aevora.graph_repository import GraphRepository
from aevora.contracts import *
E=Path(__file__).parent
main=GraphRepository.from_environment();kw=main._client.connection.connection_pool.connection_kwargs;main.close()
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name='aevora_v2_g22_atomicity_probe')
v=r.v2(TenantBinding('atomicity-probe',r.graph_name),TrustRegistry());v.initialize()
before=r.query('MATCH(n) RETURN count(n)')
error=None
try:
 r.query("MATCH(s:TenantState) SET s.epoch=99 CREATE(a:V2Record {id:'no-required-fields'}) RETURN s.epoch",read_only=False)
except Exception as e:error=type(e).__name__
after=r.query('MATCH(n) RETURN labels(n),properties(n)')
result=dict(error=error,before=before,after=after,passed=error is not None and v.state()['epoch']==0 and len(after)==1)
(E/'00_baseline/ATOMICITY_ENGINE_PROBE.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result));assert result['passed'];r.close()
