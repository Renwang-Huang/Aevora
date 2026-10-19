from pathlib import Path
import json,time,hashlib
from aevora.graph_repository import GraphRepository
E=Path(__file__).resolve().parent
for attempt in range(30):
 try:r=GraphRepository.from_environment();info=r._client.connection.info('persistence');break
 except Exception:
  if attempt==29:raise
  time.sleep(1)
# Real RDB loaded and real old legacy graph readable; no source/Oracle/test is run or changed.
assert not info['loading'];graphs=r._client.connection.execute_command('GRAPH.LIST');state=r.state_fingerprint()
out=dict(status='PASS_OWNED_MAIN_COLD_RDB_READ',graph_count=len(graphs),legacy_graph=state,persistence=info,scope='Post-SAVE main cold start at finite3GiB archive headroom; not proof of unsaved crash recovery',initial_main_memory_auxiliary='UNAVAILABLE; overwritten collector disclosed')
(E/'reports/MAIN_COLD_RECOVERY.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));r.close()
