from audit import *
from runtime import runtime as _runtime
def runtime(*args,**kwargs):return _runtime(*args,profile="REGRESSION",**kwargs)
jobs=[('epoch4-inherited-1897',runtime('tools/dev.py','test-maintainer','--output',E/'10_regression_final/inherited-1897','--owned-port','17753','--','-q','tests','aevora_core/tests','--ignore=tests/g23','--ignore=aevora_core/tests/gen2','--ignore=aevora_core/tests/g22','-p','no:cacheprovider',history=True)),('epoch4-gen2-108',runtime('tools/dev.py','test-graph-v2','--output',E/'10_regression_final/gen2-108','--owned-port','17753',history=True)),('epoch4-host58-new46',runtime('-c','import os,runpy;os.environ["AEVORA_G22_CASES"]='+repr(str(E/'02_source/cases/CASES.json'))+';runpy.run_path("tools/validation/g22_tests.py",run_name="__main__")','--output',E/'10_regression_final/host58-new46','--owned-port','17753','--','-q','aevora_core/tests/g22','tests/g23','-p','no:cacheprovider')),('epoch4-contracts-86',runtime('-m','pytest','-q','docs/gen2/g20/test_design_contracts.py','docs/gen2/g21/test_entry_contract.py','-p','no:cacheprovider','--junitxml='+str(E/'10_regression_final/CONTRACT86.xml'))),('epoch4-benchmark-cli-15',runtime('tools/dev.py','benchmark-check','--output',E/'10_regression_final/benchmark-cli-15'))]
jobs.append(('epoch4-host58-exact-root',runtime('-c','import os,runpy;os.environ["AEVORA_G22_CASES"]='+repr(str(E/'02_source/cases/CASES.json'))+';runpy.run_path("tools/dev.py",run_name="__main__")','test-host-v2','--output',E/'10_regression_final/host58-exact-root','--owned-port','17753')))
results=[]
for label,args in jobs:
 result=record(label,args);results.append(dict(label=label,exit=result));write(E/'10_regression_final/RESULTS.json',results)
print(results)
raise SystemExit(0 if all(r['exit']==0 for r in results) else 1)
