from audit import *
from runtime import runtime
jobs=[('inherited-1897',runtime('tools/dev.py','test-maintainer','--output',E/'06_regression/inherited-1897','--owned-port','17751','--','-q','tests','aevora_core/tests','--ignore=tests/g23','--ignore=aevora_core/tests/gen2','--ignore=aevora_core/tests/g22','-p','no:cacheprovider',history=True)),('gen2-108',runtime('tools/dev.py','test-graph-v2','--output',E/'06_regression/gen2-108','--owned-port','17751',history=True)),('host58-new28',runtime('-c','import os,runpy;os.environ["AEVORA_G22_CASES"]='+repr(str(E/'02_source/cases/CASES.json'))+';runpy.run_path("tools/validation/g22_tests.py",run_name="__main__")','--output',E/'06_regression/host58-new28','--owned-port','17751','--','-q','aevora_core/tests/g22','tests/g23','-p','no:cacheprovider')),('contracts-86',runtime('-m','pytest','-q','docs/gen2/g20/test_design_contracts.py','docs/gen2/g21/test_entry_contract.py','-p','no:cacheprovider','--junitxml='+str(E/'06_regression/CONTRACT86.xml'))),('benchmark-cli-15',runtime('tools/dev.py','benchmark-check','--output',E/'06_regression/benchmark-cli-15'))]
results=[]
for label,args in jobs:
 result=record(label,args);results.append(dict(label=label,exit=result));write(E/'06_regression/RESULTS.json',results)
print(results)
raise SystemExit(0 if all(r['exit']==0 for r in results) else 1)
