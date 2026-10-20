import os,json
from aevora.graph_repository import GraphRepository
from aevora.contracts import TenantBinding,TrustRegistry
from tools.validation.g21_fixture import seed,facts
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
os.environ['AEVORA_FALKORDB_GRAPH']='aevora_v2_g21_initial7'
r=GraphRepository.from_environment();r.graph_name # owned v2 selected in environment
v=r.v2(TenantBinding('tenant-test',r.graph_name),TrustRegistry());print(json.dumps(v.initialize(),default=str))
a=seed(v);state,rows=resolve_v2(v,facts(v.registry,task__shared_state_kind='sqlite_file'),'query:test',utc_now());print(json.dumps(rows[0][0],indent=2));print(v.query_receipts)
