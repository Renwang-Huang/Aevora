from pathlib import Path
import sys,json,os
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.mcp_server import ExperienceService
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.checkpoint import capture_graph
from integrations.aevora import public_runtime_context
from benchmark.manifest import load_manifest
from dataclasses import asdict
p=json.loads((E/'06_live_agent/challenge_protocol_frozen.json').read_text());os.environ['AEVORA_FALKORDB_GRAPH']=p['graph'];r=GraphRepository.from_environment();out=E/'06_live_agent/graph_snapshots_and_diffs'
try:
 c=json.loads((E/'06_live_agent/host_controlled_feedback/RESULT.json').read_text());svc=ExperienceService(run_id='pregen2-final-host-only-probe',public_context=public_runtime_context(asdict(load_manifest('D'))),repository=r)
 q=svc.resolve_experience({});b=svc.build_evidence_bundle(c['published_experience_id'],q['query_id']);assert b['publication_lifecycle']['state']=='PUBLISHED'
 write(out/'FINAL_HOST_RETRIEVAL_NOT_MODEL.json',{'status':'PASS_HOST_ONLY_NOT_S2_INHERITANCE','query':q,'bundle':b,'at':now(),'evidence_tier':'TRUSTED_HOST_GRAPH_CONTROL','S2_success_upgraded':False})
 write(out/'FINAL_AFTER_S2.json',capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION));saved=r._client.connection.save();assert saved is True
 write(out/'FINAL_SAVE.json',{'at':now(),'save':saved,'graph':r.graph_name,'port':17705,'scope':'Actual latest owned RDB SAVE; no crash-tail guarantee','redis_version':r._client.connection.info('server')['redis_version'],'modules':r._client.connection.info('modules')})
finally:r.close()
