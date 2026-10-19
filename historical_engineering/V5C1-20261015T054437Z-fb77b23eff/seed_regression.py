import os
from aevora.graph_repository import GraphRepository
name=os.environ['AEVORA_FALKORDB_GRAPH'];os.environ['AEVORA_FALKORDB_GRAPH']='aevora_v5c_legacy_0567cecf24ef43009cf5443f7d667a84'
r=GraphRepository.from_environment();r._graph.copy(name);r.close();os.environ['AEVORA_FALKORDB_GRAPH']=name
r=GraphRepository.from_environment();assert r.experience_ids();print(r.state_fingerprint());r.close()
