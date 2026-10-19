from audit import *
from runtime import runtime
jobs=[('epoch2-inherited-1897',runtime('tools/dev.py','test-maintainer','--output',E/'07_regression_epoch2/inherited-1897','--owned-port','17751','--','-q','tests','aevora_core/tests','--ignore=tests/g23','--ignore=aevora_core/tests/gen2','--ignore=aevora_core/tests/g22','-p','no:cacheprovider',history=True)),('epoch2-gen2-108',runtime('tools/dev.py','test-graph-v2','--output',E/'07_regression_epoch2/gen2-108','--owned-port','17751',history=True)),('epoch2-host58-new44',runtime('-c','import os,runpy;os.environ["AEVORA_G22_CASES"]='+repr(str(E/'02_source/cases/CASES.json'))+';runpy.run_path("tools/validation/g22_tests.py",run_name="__main__")','--output',E/'07_regression_epoch2/host58-new44','--owned-port','17751','--','-q','aevora_core/tests/g22','tests/g23','-p','no:cacheprovider')),('epoch2-contracts-86',runtime('-m','pytest','-q','docs/gen2/g20/test_design_contracts.py','docs/gen2/g21/test_entry_contract.py','-p','no:cacheprovider','--junitxml='+str(E/'07_regression_epoch2/CONTRACT86.xml'))),('epoch2-benchmark-cli-15',runtime('tools/dev.py','benchmark-check','--output',E/'07_regression_epoch2/benchmark-cli-15'))]
jobs.append(('epoch2-host58-exact-root',runtime('-c','import os,runpy;os.environ["AEVORA_G22_CASES"]='+repr(str(E/'02_source/cases/CASES.json'))+';runpy.run_path("tools/dev.py",run_name="__main__")','test-host-v2','--output',E/'07_regression_epoch2/host58-exact-root','--owned-port','17751')))
results=[]
for label,args in jobs:
 result=record(label,args);results.append(dict(label=label,exit=result));write(E/'07_regression_epoch2/RESULTS.json',results)
print(results)
raise SystemExit(0 if all(r['exit']==0 for r in results) else 1)
