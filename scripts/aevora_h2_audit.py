#!/usr/bin/env python3
"""H2 isolated source/history capture and actual command receipts; no secret reads."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import argparse
import json
import os
import shutil
import stat
import subprocess
import uuid
import xml.etree.ElementTree as ET
from scripts.aevora_h1_audit import record
from scripts.aevora_h2_junit import check_junit
ROOT=Path(__file__).resolve().parents[1]
H1=ROOT/'aevora_validation/20261011T051334Z-3e7fe273-3a17-4891-a6b2-4afb25376288'
H1E=ROOT/'aevora_validation/audit_exports'/H1.name
SOURCE_DIRS=('app','benchmark','evaluator','integrations','scripts','tests','docs','benchmark_roadmap','aevora_core')
SUFFIXES={'.py','.md','.json','.diff','.toml','.yaml','.yml','.txt','.sh','.sql','.cypher','.csv'}
NON_SOURCE_DIRECTORIES={'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.tox','node_modules','build','dist'}
def source_path_allowed(relative):
 parts=Path(relative).parts
 return not any(x in NON_SOURCE_DIRECTORIES or x.endswith('.egg-info') for x in parts) and (Path(relative).suffix in SUFFIXES or Path(relative).name in {'python312','aevora-python','aevora-h2-python','orderflow'})
def digest(path):
 h=sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(path,value):
 with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False);f.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
def sources():
 rows={}
 for directory in SOURCE_DIRS:
  for current, directories, files in os.walk(ROOT/directory,followlinks=False):
   directories[:]=sorted(x for x in directories if x not in NON_SOURCE_DIRECTORIES and not x.endswith('.egg-info') and not (Path(current)/x).is_symlink())
   for name in sorted(files):
    p=Path(current)/name
    if p.is_file() and not p.is_symlink() and source_path_allowed(p.relative_to(ROOT)):
     rows[p.relative_to(ROOT).as_posix()]={'sha256':digest(p),'mode':stat.S_IMODE(p.stat().st_mode)}
 for p in ROOT.iterdir():
  if p.is_file() and not p.is_symlink() and (p.suffix in {'.md','.toml'} or p.name=='.gitignore'):
   rows[p.name]={'sha256':digest(p),'mode':stat.S_IMODE(p.stat().st_mode)}
 return dict(sorted(rows.items()))
def capture():
 A=ROOT/'aevora_validation'/('H2-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+str(uuid.uuid4()));A.mkdir()
 base=A/'g0';base.mkdir();rows=sources()
 for rel,row in rows.items():
  dest=base/'source_snapshot'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest);dest.chmod(row['mode'])
 tree=sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 write(base/'BASELINE_SOURCES.json',{'files':rows,'source_tree_sha256':tree,'recorded_at':now(),'qualification':'H1-post-live-fix current dirty source, not historical HEAD'})
 history=json.loads((H1/'g0/PROTECTED_HISTORY.json').read_text())
 seal=json.loads((H1/'EVIDENCE_MANIFEST.json').read_text())
 for rel,oldsha in seal['ordinary_files_sha256'].items():
  p=H1/rel;actual=digest(p);assert actual==oldsha,'H1 sealed file changed: '+rel;history[p.relative_to(ROOT).as_posix()]=actual
 for p in [H1/'EVIDENCE_MANIFEST.json',H1/'SHA256SUMS',*H1E.rglob('*'),*ROOT.glob('AEVORA_H1*')]:
  if p.is_file() and not p.is_symlink():history[p.relative_to(ROOT).as_posix()]=digest(p)
 assert digest(H1E/'aevora-h1-audit-lite.zip')=='d38db23087f702b5f5320428b5e622a56de7aa2eacad25ad4ed8373e0bc4708e'
 write(base/'PROTECTED_HISTORY.json',history)
 cases=list(ET.parse(H1/'H1_FINAL_RELEASE_JUNIT.xml').getroot().iter('testcase'))
 ids=sorted(t.attrib.get('classname','')+'::'+t.attrib['name'] for t in cases);assert len(ids)==1214
 write(base/'INHERITED_TEST_IDENTITIES.json',{'identities':ids,'source':str((H1/'H1_FINAL_RELEASE_JUNIT.xml').relative_to(ROOT)),'junit_sha256':digest(H1/'H1_FINAL_RELEASE_JUNIT.xml')})
 truth=json.loads((ROOT/'m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/FROZEN_TASK_TRUTH.json').read_text())['files'];write(base/'FROZEN_TASK_TRUTH.json',truth)
 for p,expected in history.items():assert digest(ROOT/p)==expected,'Historical byte change: '+p
 for p,expected in truth.items():assert digest(ROOT/p)==expected,'Historical task truth change: '+p
 git={}
 for name,argv in [('status',['git','status','--short','--branch']),('head',['git','rev-parse','HEAD']),('diff',['git','diff','--binary']),('branch',['git','branch','--show-current'])]:
  r=subprocess.run(argv,cwd=ROOT,capture_output=True);(base/('git_'+name+'.txt')).write_bytes(r.stdout);git[name]={'argv':argv,'exit_code':r.returncode,'stdout_sha256':digest(base/('git_'+name+'.txt'))}
 write(base/'BASELINE.json',{'recorded_at':now(),'source_tree_sha256':tree,'source_files':len(rows),'historical_files':len(history),'original_tests':1214,'task_truth_files':len(truth),'git':git,'H1_live_manifest_sha256':digest(H1/'release_admission_v2/SOURCE_TRUST_MANIFEST.json'),'H1_post_live_broker_sha256':digest(ROOT/'aevora_core/src/aevora/mcp_broker.py'),'H1_archive_verified':'ALL_CAPTURED_REGULAR_BYTES','H1_handoff':'NOT_FOUND_IN_WORKSPACE','historical_results':'UNCHANGED; not new H2 test results'})
 pointer=ROOT/'aevora_validation/H2_CURRENT';pointer.write_text(str(A)+'\n')
 print(json.dumps({'archive':str(A),'source_tree_sha256':tree,'sources':len(rows),'protected_history_files':len(history)}))
def integrity(A,junit,output):
 rows=json.loads((A/'g0/BASELINE_SOURCES.json').read_text())['files'];history=json.loads((A/'g0/PROTECTED_HISTORY.json').read_text());truth=json.loads((A/'g0/FROZEN_TASK_TRUTH.json').read_text());checks={}
 for name,files in [('history',history),('task_truth',truth),('inherited_test_sources',{p:v['sha256'] for p,v in rows.items() if p.startswith(('tests/','aevora_core/tests/'))})]:
  bad=[p for p,s in files.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=s];checks[name]={'file_count':len(files),'mismatches':bad,'status':'PASS' if not bad else 'FAIL'}
 required=json.loads((A/'g0/INHERITED_TEST_IDENTITIES.json').read_text())['identities']
 checks['original_1214_tests']=check_junit(junit,required)
 v={'recorded_at':now(),'checks':checks,'status':'PASS' if all(x['status']=='PASS' for x in checks.values()) else 'FAIL','authority':'local byte consistency; not third-party attestation'};write(output,v);print(json.dumps(v));return 0 if v['status']=='PASS' else 1
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='operation',required=True);s.add_parser('capture');r=s.add_parser('record');r.add_argument('archive',type=Path);r.add_argument('label');r.add_argument('argv',nargs=argparse.REMAINDER);i=s.add_parser('integrity');i.add_argument('archive',type=Path);i.add_argument('junit',type=Path);i.add_argument('output',type=Path)
 a=p.parse_args()
 if a.operation=='capture':capture()
 elif a.operation=='record':raise SystemExit(record(a.archive.absolute(),a.label,a.argv[1:] if a.argv[:1]==['--'] else a.argv))
 else:raise SystemExit(integrity(a.archive.absolute(),a.junit,a.output))
if __name__=='__main__':main()
