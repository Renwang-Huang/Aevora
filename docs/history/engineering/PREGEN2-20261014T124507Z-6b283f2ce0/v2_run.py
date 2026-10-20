from runtime import *
import xml.etree.ElementTree as ET,collections,csv,shutil
seed="from aevora.graph_repository import GraphRepository;from aevora.historical_import import import_verified_history;from pathlib import Path;p=Path("+repr(str(R/'m1_validation'))+");a=Path((p/'CURRENT').read_text().strip());a=a if a.is_absolute() else p/a;r=GraphRepository.from_environment();r.initialize();print(import_verified_history(r,a));r.close()"
assert record('v2-owned-historical-import',runtime('-c',seed,history=True))==0
code=record('v2-full-1836-attempt1',runtime('tools/dev.py','test-maintainer','--output',str(E/'02_regression/attempts/attempt1'),'--owned-port','17705',history=True))
out=E/'02_regression/attempts/attempt1';x=ET.parse(out/'JUNIT.xml');cases=list(x.iter('testcase'));ids=[c.get('classname','')+'::'+c.get('name','') for c in cases];expected=(E/'02_regression/expected_test_ids.txt').read_text().splitlines()
actual=collections.Counter(ids);base=collections.Counter(expected)
(E/'02_regression/actual_test_ids.txt').write_text('\n'.join(sorted(ids))+'\n')
diff={'missing':list((base-actual).elements()),'extra':list((actual-base).elements()),'duplicates':{k:v for k,v in actual.items() if v>1}}
write(E/'02_regression/id_diff.json',diff)
result={'at':now(),'status':'PASS' if code==0 and len(ids)==1836 and len(actual)==1836 and actual==base and not any(c.find(n) is not None for c in cases for n in ['failure','error','skipped']) else 'FAIL','exit_code':code,'cases':len(ids),'unique_ids':len(actual),'failures':sum(c.find('failure') is not None for c in cases),'errors':sum(c.find('error') is not None for c in cases),'skips':sum(c.find('skipped') is not None for c in cases),'identity_exact':actual==base,'HISTORY_DEPENDENCY':'YES','junit_sha256':sha(out/'JUNIT.xml'),'expected_ids_sha256':sha(E/'02_regression/expected_test_ids.txt'),'actual_ids_sha256':sha(E/'02_regression/actual_test_ids.txt'),'source_unchanged':json.loads((out/'RUNTIME_SOURCE_EPOCH.json').read_text())['unchanged']}
write(E/'02_regression/regression_summary.json',result)
shutil.copyfile(out/'JUNIT.xml',E/'02_regression/junit_full.xml')
print(json.dumps(result),flush=True)
# Retain regression failure; separately collect independent Benchmark contracts.
cli=record('v2-cli-15',runtime('tools/dev.py','benchmark-check','--output',str(E/'03_benchmark/cli')))
dv=record('v2-dv02-independent',runtime('tools/dev.py','dv02-check','--output',str(E/'03_benchmark/dv02')))
write(E/'03_benchmark/COMMAND_RESULT.json',{'cli_exit':cli,'dv02_exit':dv,'at':now()})
print('V2 finished',result['status'],cli,dv)
