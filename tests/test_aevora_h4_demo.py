"""Portable product demo executes only pinned public replay and ordinary read paths."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def test_real_portable_replay_demo_contains_three_distinct_cases():
    p=subprocess.run([sys.executable,str(ROOT/'examples/observatory/demo.py'),'--root',str(ROOT/'examples/observatory'),'--sha256',sha256((ROOT/'examples/observatory/hero_scenario_contract.json').read_bytes()).hexdigest()],capture_output=True,text=True,check=False)
    assert p.returncode==0
    v=json.loads(p.stdout);assert v['mode']=='REPLAY' and len(v['cases'])==3
    assert v['experience_lifecycle']['native_children']==3 and v['experience_lifecycle']['necessary_test_counts']['passed']==14
    assert v['ordinary_pilot']['governance']['passed']==v['ordinary_pilot']['raw_memory']['passed']==7
    assert v['causal_benefit']=='UNKNOWN'

def test_real_demo_rejects_untrusted_pin():
    p=subprocess.run([sys.executable,str(ROOT/'examples/observatory/demo.py'),'--root',str(ROOT/'examples/observatory'),'--sha256','0'*64],capture_output=True,text=True,check=False)
    assert p.returncode!=0 and not p.stdout
