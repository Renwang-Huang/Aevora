from audit import *
from runtime import runtime as original

def runtime(*args,**kwargs):return original(*args,profile='REGRESSION',history=True,**kwargs)
base_cases=E.parent/'G23-20261016T021142Z-1e5e8e1af0/02_source/cases/CASES.json'
jobs=[
 ('rerun-inherited-1897',runtime('tools/dev.py','test-maintainer','--output',E/'05_regression/inherited-1897','--owned-port','19063','--','-q','tests','aevora_core/tests','--ignore=tests/g23','--ignore=tests/test_final_public_product.py','--ignore=aevora_core/tests/gen2','--ignore=aevora_core/tests/g22','-p','no:cacheprovider')),
 ('rerun-graph-v2-108',runtime('tools/dev.py','test-graph-v2','--output',E/'05_regression/graph-v2-108','--owned-port','19063')),
 ('rerun-host58-native46',runtime('-c','import os,runpy;os.environ["AEVORA_G22_CASES"]='+repr(str(base_cases))+';runpy.run_path("tools/validation/g22_tests.py",run_name="__main__")','--output',E/'05_regression/host58-native46','--owned-port','19063','--','-q','aevora_core/tests/g22','tests/g23','-p','no:cacheprovider')),
 ('rerun-contracts86',runtime('-m','pytest','-q','docs/gen2/g20/test_design_contracts.py','docs/gen2/g21/test_entry_contract.py','-p','no:cacheprovider','--junitxml='+str(E/'05_regression/CONTRACT86.xml'))),
 ('rerun-benchmark-cli15',runtime('tools/dev.py','benchmark-check','--output',E/'05_regression/benchmark-cli15')),
]
rows=[]
for label,cmd in jobs:
 code=record(label,cmd);rows.append(dict(label=label,exit=code));write(E/'05_regression/RESULTS.json',rows)
print(rows);raise SystemExit(0 if all(r['exit']==0 for r in rows) else 1)
