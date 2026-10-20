from pathlib import Path
import json,os,sys,uuid,hashlib
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from benchmark.h2_cli import register_h2
register_h2()
from benchmark.registry import get_episode
from evaluator.suites import SUITES
from integrations.aevora import public_runtime_context
from aevora.graph_repository import GraphRepository
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION,digest
P=E/'owned_runtime/source';manifest=json.loads((P/'benchmark/scenarios/D-V02/public.json').read_text());registration=get_episode('D-V02');fixture=E/'04_live/initial_public_fixture_attempt2';registration.build(fixture,'v02')
publicfiles={str(p.relative_to(fixture)):sha(p) for p in sorted(fixture.rglob('*')) if p.is_file() and not p.is_symlink()}
private={str(p.relative_to(P)):sha(p) for p in sorted((P/'evaluator').rglob('*')) if p.is_file() and not p.is_symlink()}
os.environ['AEVORA_FALKORDB_GRAPH']='aevora_v5c_live_0a70f0ccc4204a75846e00199c2923c0';main=GraphRepository.from_environment();state=capture_graph(main,schema_version=LIFECYCLE_SCHEMA_VERSION)
assert state['graph_sha256']=='ad8d4c6fbe7b72d2093d08236f42a325b6221a929bdb08f4bafa0c057aa2c21d'
name='aevora_v5c1_live_'+uuid.uuid4().hex;main._graph.copy(name);main.close();os.environ['AEVORA_FALKORDB_GRAPH']=name;r=GraphRepository.from_environment();copied=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);assert {k:v for k,v in copied.items() if k!='graph_name'}=={k:v for k,v in state.items() if k!='graph_name'}
write(E/'04_live/INITIAL_GRAPH.json',{'graph':name,'at':now(),'complete_snapshot':copied,'exact_original_content_excluding_owned_graph_name':True,'all_old_competitors_retained':r.experience_ids()});r.close()
write(E/'04_live/FROZEN_EXPERIMENT_INPUTS.json',{'at':now(),'public_manifest_sha256':sha(P/'benchmark/scenarios/D-V02/public.json'),'pinned_public_facts':public_runtime_context(manifest),'fixture_version':registration.fixture_version,'suite_version':SUITES['episode_d_v02'].version,'public_fixture_files':publicfiles,'public_tests':{str(p.relative_to(P)):sha(p) for p in registration.public_tests},'private_oracle_source_digest':digest(private),'private_files':private,'patch_freeze_sha256':sha(E/'02_fix/PATCH_FREEZE.json'),'s1_episode':'D-V02','s2_episode':'D-V02','variant':'v02','request_budget':None,'timeout_seconds':None,'dollar_budget':None,'token_budget':None,'agent_mode':'single','model':'gpt-5.6-terra','reasoning_effort':'max','max_request_concurrency':2,'no_look_at_new_agent_patch':True,'fixture_is_original_buggy_baseline_not_submission':True,'scope':'PREREGISTRATION_METADATA_NOT_PARTICIPANT_PROMPT'})
print('PREREGISTERED_INPUTS',name, len(publicfiles),flush=True)
