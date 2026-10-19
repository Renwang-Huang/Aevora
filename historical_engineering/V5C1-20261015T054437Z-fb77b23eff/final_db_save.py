from pathlib import Path
import sys,json,importlib.metadata,sqlite3,platform
E=Path(__file__).resolve().parent;sys.path.insert(0,str(E))
from audit import write,now,sha
from aevora.graph_repository import GraphRepository
from aevora.checkpoint import capture_graph,save_boundary
from aevora.models import LIFECYCLE_SCHEMA_VERSION
r=GraphRepository.from_environment()
try:
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);expected=json.loads((E/'05_graph/after_restart/graph_after.json').read_text());assert before==expected
 boundary=save_boundary(r,writers_quiesced=True,schema_version=LIFECYCLE_SCHEMA_VERSION)
 modules=r._client.connection.execute_command('MODULE','LIST')
 def safe(v):
  if isinstance(v,bytes):return v.decode()
  if isinstance(v,(tuple,list)):return [safe(x) for x in v]
  if isinstance(v,dict):return {safe(k):safe(x) for k,x in v.items()}
  return v
 write(E/'05_graph/FINAL_SAVE_BOUNDARY.json',boundary)
 write(E/'06_audit/FINAL_RUNTIME_VERSIONS.json',{'at':now(),'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'installed_packages':{k:importlib.metadata.version(k) for k in ['aevora-core','aevora-console','orderflow-incident-lab','mcp','pydantic','falkordb','redis','anyio','pytest']},'actual_redis_modules':safe(modules),'redis_server':r._client.connection.info('server')['redis_version'],'owned_rdb_sha256':sha(E/'owned_db_data/dump.rdb'),'owned_rdb_bytes':(E/'owned_db_data/dump.rdb').stat().st_size})
 print('FINAL_OWNED_GRAPH_SAVE_VERIFIED',before['node_count'],before['edge_count'])
finally:r.close()
