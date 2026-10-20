from pathlib import Path
import sys,os,json
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle
from aevora.experience_resolver import ExperienceResolver
from aevora.historical_import import import_verified_history,public_context
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.checkpoint import capture_graph
from scripts.aevora_h2_graph_e2e import RawCommands
protocol=json.loads((E/'06_live_agent/challenge_protocol_frozen.json').read_text());os.environ['AEVORA_FALKORDB_GRAPH']=protocol['graph']
out=E/'06_live_agent/graph_snapshots_and_diffs';out.mkdir(mode=0o700);r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r)
try:
 CandidateLifecycle(r).initialize();empty=ExperienceResolver(r).resolve(public_context('multi_process_shared_sqlite'),persist_snapshots=False);assert empty['candidates']==[];write(out/'EMPTY_BEFORE_SEED.json',empty)
 p=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/orderflow_incident_lab/m1_validation');a=Path((p/'CURRENT').read_text().strip());a=a if a.is_absolute() else p/a
 seed=import_verified_history(r,a);write(out/'SEED_RECEIPT.json',seed)
 snap=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'BEFORE_S1.json',snap);write(out/'SEED_SCOPE.json',{'at':now(),'status':'PASS','graph':r.graph_name,'source':'Four actually historical verified outcomes; protected read-only original corpus','classification':'TRUSTED_HOST_VERIFIED_HISTORY_NOT_NEW_AGENT','new_model_outcomes':0,'snapshot_sha256':sha(out/'BEFORE_S1.json')})
 print('V5 actual authorized graph initialized',r.graph_name)
finally:raw.close();r.close()
