from pathlib import Path
import sys,time,subprocess,json
E=Path(__file__).parent;sys.path.insert(0,str(E));from audit import *
from runtime import runtime
O=E/'04_security/outage-recovery';O.mkdir(exist_ok=True)
outer=[sys.executable,'-B',str(E/'runtime.py'),'actual-db-outage-prepare','--',str(E/'outage_phase.py'),'prepare']
with (O/'controller-child.stdout').open('x') as out,(O/'controller-child.stderr').open('x') as err:
 proc=subprocess.Popen(outer,cwd=E,stdout=out,stderr=err)
 deadline=time.monotonic()+60
 while not (O/'WAIT_FOR_DB_STOP.json').exists():
  if proc.poll() is not None:raise RuntimeError('Prepare child exited before outage boundary')
  if time.monotonic()>deadline:raise TimeoutError('Prepare child not ready')
  time.sleep(.05)
 assert record('owned-db-stop-during-prepare',['docker','stop','--time','5','aevora-g22-88fad40ffd'],cwd=E)==0
 (O/'DB_STOPPED_GO').write_text(now())
 code=proc.wait(timeout=20);assert code==0,code
 assert json.loads((O/'OUTAGE_OBSERVED.json').read_text())['status']=='EXPECTED_DB_FAILURE_OBSERVED'
assert record('owned-db-start-after-outage',['docker','start','aevora-g22-88fad40ffd'],cwd=E)==0
assert record('owned-db-ready-after-outage',runtime(E/'owned_restart_ready.py'))==0
assert record('owned-preparation-recovery',runtime(E/'outage_phase.py','recover'))==0
assert json.loads((O/'RECOVERED.json').read_text())['save'] is True
assert record('owned-db-stop-for-cold-rdb',['docker','stop','--time','5','aevora-g22-88fad40ffd'],cwd=E)==0
assert record('owned-db-start-cold-rdb',['docker','start','aevora-g22-88fad40ffd'],cwd=E)==0
assert record('owned-db-ready-cold-rdb',runtime(E/'owned_restart_ready.py'))==0
assert record('owned-rdb-idempotent-recovery',runtime(E/'outage_phase.py','verify'))==0
write(O/'CONTROLLER_RESULT.json',dict(status='PASS',actual_database_outage=True,graceful_rdb_restart=True,before_fence_invisible=True,replay_no_second_commit=True,aof='KNOWN_LIMITATION_139',power_loss_unsaved='UNVERIFIED'))
print('owned outage, retry and cold RDB replay passed')
