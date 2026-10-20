from pathlib import Path
import json,time
from aevora.graph_repository import GraphRepository
E=Path(__file__).parent;deadline=time.monotonic()+90;attempts=[]
while True:
 try:
  r=GraphRepository.from_environment();info=r._client.connection.info('persistence');r.close();attempts.append(dict(loading=info.get('loading'),at=time.time()))
  if not info.get('loading'):break
 except Exception as e:attempts.append(dict(error=type(e).__name__,at=time.time()))
 if time.monotonic()>deadline:raise TimeoutError('Owned RDB load did not finish')
 time.sleep(.2)
(E/'04_security/outage-recovery-saved'/('READY_'+str(time.time_ns())+'.json')).write_text(json.dumps(attempts));print('owned DB ready')
