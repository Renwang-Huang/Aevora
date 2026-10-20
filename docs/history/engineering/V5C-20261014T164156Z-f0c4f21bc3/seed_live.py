from runtime import *
graph=json.loads((E/'00_environment/LIVE_GRAPH_ID.json').read_text())['graph']
code="from aevora.graph_repository import GraphRepository;from aevora.models import LIFECYCLE_SCHEMA_VERSION;from aevora.historical_import import import_verified_history;from pathlib import Path;import json;p=Path("+repr(str(R/'m1_validation'))+");a=Path((p/'CURRENT').read_text().strip());a=a if a.is_absolute() else p/a;r=GraphRepository.from_environment();r.initialize(schema_version=LIFECYCLE_SCHEMA_VERSION);print(json.dumps(import_verified_history(r,a)));print(json.dumps(r.state_fingerprint()));r.close()"
assert record('c1-live-owned-schema-seed-retry1',runtime('-c',code,history=True,graph=graph))==0
assert record('c1-schema12-context-real-wire',runtime('-m','pytest','-q','aevora_core/tests/test_v5c_context_contract.py','--junitxml='+str(E/'01_c1_repairs/context-schema12.xml'),graph=graph))==0
print('LIVE_SCHEMA12_SEEDED_AND_CONTEXT_CHECKED',flush=True)
