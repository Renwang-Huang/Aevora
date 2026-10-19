from audit import *
import ast,csv,shutil,sys,xml.etree.ElementTree as ET

def git(p,*a):return subprocess.check_output(['git','--no-optional-locks','-C',str(p),*a],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True).strip()
old=BASE.parents[1];expected=json.loads((old/'00_baseline/BASELINE_IDENTITY.json').read_text())['source547_sha256'];pin=json.loads((old/'source/SOURCE_TRUST_MANIFEST.json').read_text())
assert git(W,'rev-parse','HEAD')=='737f1746631774251a2c504aaf0ceafd9c3ff0c0' and git(W,'rev-parse','HEAD^{tree}')=='7fad4fffdad4c9a85ae9e521928b6a6592a4dcb9'
assert not git(W,'status','--porcelain=v1') and len(expected)==547 and all(sha(W/n)==h for n,h in expected.items())
assert git(BASE,'rev-parse','HEAD')==C['base_head'] and git(BASE,'rev-parse','HEAD^{tree}')==C['base_tree'] and not git(BASE,'status','--porcelain=v1')
assert len(pin['files'])==551 and all(sha(BASE/n.removeprefix('frozen_source_snapshot/'))==h for n,h in pin['files'].items())
assert git(P,'rev-parse','HEAD')==C['base_head'] and not git(P,'status','--porcelain=v1') and all(sha(P/n.removeprefix('frozen_source_snapshot/'))==h for n,h in pin['files'].items())
for a,b in [('737f1746631774251a2c504aaf0ceafd9c3ff0c0','f016a825be67c0d30c8dcdb7f6b046c26d65ca95'),('f016a825be67c0d30c8dcdb7f6b046c26d65ca95',C['base_head'])]:assert subprocess.run(['git','--git-dir',C['git_common'],'merge-base','--is-ancestor',a,b]).returncode==0
assert not (Path(C['git_common'])/'objects/info/alternates').exists()
# Native logs/results are historical evidence, explicitly NOT new execution.
for n in ['03_regression/RAW_JUNIT.xml','03_regression/REGRESSION_IDENTITY.json','03_regression/STRICT_IDENTITY_RECHECK.json','06_audit/FINAL_SOURCE_IDENTITY.json','06_audit/FINAL_RUNTIME_VERSIONS.json','06_audit/LIMITATIONS_AND_UNKNOWN.md','06_audit/FINAL_DELIVERY_RECEIPT.json','06_audit/V5C1_FULL_VALIDATION_REPORT.md']:
 q=E/'historical_receipts'/Path(n).name;shutil.copyfile(old/n,q)
cs=list(ET.parse(old/'03_regression/RAW_JUNIT.xml').getroot().iter('testcase'));assert len(cs)==1897 and all(not list(x) for x in cs)
review_candidates=[p for root in [W.parent, W] for p in root.glob('*V5C1*Review*.md')]
write(E/'BASELINE_RECEIPT.json',{'schema':'aevora.g20.baseline/1','at':now(),'status':'PASS_SOURCE_IDENTITY_NOT_TEST_RERUN','main_head':git(W,'rev-parse','HEAD'),'main_tree':git(W,'rev-parse','HEAD^{tree}'),'main_clean':True,'main547_verified':547,'base_head':C['base_head'],'base_tree':C['base_tree'],'base551_verified':551,'base_clean':True,'new_worktree':str(P),'new_branch':git(P,'branch','--show-current'),'new_head':git(P,'rev-parse','HEAD'),'new_tree':git(P,'rev-parse','HEAD^{tree}'),'new_clean_before_design':True,'independent_git_objects_no_hardlinks_no_alternates':True,'ancestry_verified':True,'historical1897_junit_sha256':sha(old/'03_regression/RAW_JUNIT.xml'),'historical_test_count':1897,'tests_rerun_here':False,'original_schema_oracle_writes':False,'new_independent_review_candidates':[str(x) for x in review_candidates],'independent_review_status':'UNAVAILABLE_EXACT_REVIEW_UNLESS_SEPARATELY_FOUND','input_task_sha256':sha(W.parent/'Aevora_Gen2_G20_Final_Architecture_and_Contract_Freeze_Codex_Taskbook_2026-10-15.md')})
paths=[]
for folder in ['aevora_core/src/aevora','integrations','benchmark','evaluator','app','aevora_maintainer','console/src/aevora_observatory','tools']:
 paths.extend(p for p in (P/folder).glob('*.py'))
records=[]
for p in sorted(set(paths)):
 n=str(p.relative_to(P));tree=ast.parse(p.read_text());symbols=[];imports=[]
 def walk(nodes,prefix=''):
  for x in nodes:
   if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
    symbol=prefix+x.name;symbols.append({'symbol':symbol,'line':x.lineno,'end_line':x.end_lineno,'kind':type(x).__name__})
    if isinstance(x,ast.ClassDef):walk(x.body,symbol+'.')
 walk(tree.body)
 for x in ast.walk(tree):
  if isinstance(x,ast.Import):imports.extend(a.name for a in x.names)
  elif isinstance(x,ast.ImportFrom):imports.append('.'*x.level+(x.module or ''))
 records.append({'path':n,'sha256':sha(p),'lines':len(p.read_text().splitlines()),'symbols':symbols,'imports':sorted(set(imports))})
write(E/'source_audit/SYMBOL_AND_IMPORT_INDEX.json',{'source_commit':C['base_head'],'source_tree':C['base_tree'],'classification':'STATIC_AST_NOT_RUNTIME_EXECUTION','files':records})
with (E/'source_audit/FILE_SYMBOL_SUMMARY.csv').open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(['path','sha256','lines','symbols'])
 for r in records:writer.writerow([r['path'],r['sha256'],r['lines'],';'.join(x['symbol']+':'+str(x['line']) for x in r['symbols'])])
print('BASELINE547_551_PASS_AST',len(records))
