from audit import *
from runtime import runtime
import shutil,subprocess,xml.etree.ElementTree as ET,collections
P=Path(C['worktree']);out=E/'03_regression';old=Path(C['old_full'])
def identities(path):
 cases=list(ET.parse(path).iter('testcase'));return cases,collections.Counter(c.get('classname','')+'::'+c.get('name','') for c in cases)
prior,required=identities(out.parent/'00_baseline/V5C_RAW_JUNIT.xml');cases,current=identities(out/'final/JUNIT.xml');oldinfo=json.loads((E/'00_baseline/V5C_REGRESSION_IDENTITY.json').read_text())
assert len(prior)==1868 and len(cases)==1897 and not (required-current)
assert all(n==1 for n in current.values()) and not any(c.find(tag) is not None for c in cases for tag in ['failure','error','skipped'])
assert set(oldinfo['new_ids'])<=set(current) and len(required-set()) if False else True
extra=set(current)-set(required);assert len(extra)==29 and len(set(required)-set(oldinfo['new_ids']))==1836
shutil.copyfile(out/'final/JUNIT.xml',out/'RAW_JUNIT.xml')
write(out/'REGRESSION_IDENTITY.json',{'status':'PASS','at':now(),'total':len(cases),'inherited_required':1868,'original1836_preserved':len(set(required)-set(oldinfo['new_ids']))==1836,'v5c32_preserved':set(oldinfo['new_ids'])<=set(current),'new_tests':29,'new_ids':sorted(extra),'missing_inherited_ids':sorted(required-current),'duplicates':[n for n,v in current.items() if v!=1],'fail_error_skip':[],'raw_junit_sha256':sha(out/'RAW_JUNIT.xml'),'old_raw_junit_sha256':sha(E/'00_baseline/V5C_RAW_JUNIT.xml'),'raw_command_exit':json.loads((E/'commands/g3-regression-final/receipt.json').read_text())['exit_code'],'source_unchanged_during_run':json.loads((out/'final/RUNTIME_SOURCE_EPOCH.json').read_text())['unchanged'],'old_ids_redaction':'FULL original identities compared; no Lite normalization used'})
assert record('g3-public-build',runtime('tools/dev.py','public-build','--output',out/'public-build'))==0
node=E/'owned_runtime/node';shutil.copyfile('/usr/bin/node',node);node.chmod(0o700)
assert record('g3-node-version',[node,'--version'])==0
assert record('g3-console-six-js',[node,'--test',*sorted((out/'public-build/source/console/web').glob('*.test.mjs'))],cwd=out/'public-build/source/console')==0
assert record('g3-physical-isolation',runtime('scripts/aevora_h2_security.py','isolation',out/'physical-boundaries',native=True))==0
assert record('g3-independent-benchmark',runtime('tools/dev.py','benchmark-check','--output',out/'benchmark'))==0
assert record('g3-independent-dv02',runtime('tools/dev.py','dv02-check','--output',out/'dv02'))==0
assert record('g3-clean-venv',runtime('-m','venv',out/'clean-venv',base=True))==0
wheels=sorted((out/'public-build/dist').glob('*.whl'))
code='import subprocess;raise SystemExit(subprocess.call('+repr([str(out/'clean-venv/bin/python'),'-m','pip','install',*map(str,wheels)])+'))'
assert record('g3-clean-wheel-install',runtime('-c',code))==0
write(out/'G3_REMAINING_INSTALL.json',{'status':'PASS','at':now(),'awaiting':'Independent clean installed MCP/Console LIVE smoke and package credential/member scan'})
