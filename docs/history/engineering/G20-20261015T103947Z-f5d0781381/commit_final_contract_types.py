from audit import *
import json,xml.etree.ElementTree as ET,shutil
D=P/'docs/gen2/g20';p=D/'CONTRACT_FREEZE_INDEX.json';shutil.copyfile(p,E/'source_audit/CONTRACT_FREEZE_INDEX.csv_normalized_commit.json')
cs=list(ET.parse(E/'checks/release-final/JUNIT.xml').getroot().iter('testcase'));assert len(cs)==59 and all(not list(c) for c in cs)
x=json.loads(p.read_text());x['created_at']=now();x['supersedes_design_commit']=subprocess.check_output(['git','-C',str(P),'rev-parse','HEAD'],text=True).strip();x['changes_since_prior_freeze']='Strengthen registered fact types, explicitly map complete17-field legacy Host vocabulary and preserve strict schema checks; no production source changes.'
x['files']={str(q.relative_to(D)):{'sha256':sha(q),'bytes':q.stat().st_size} for q in sorted(D.rglob('*')) if q.is_file() and q.name!='CONTRACT_FREEZE_INDEX.json'};x['current_design_checks'].update(passed=len(cs),junit_sha256=sha(E/'checks/release-final/JUNIT.xml'));p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
assert record('g20-stage-final-typed-contracts',['git','-C',P,'add','--','docs/gen2/g20'])==0
assert record('g20-final-typed-diff-check',['git','-C',P,'diff','--cached','--check'])==0
assert record('g20-final-contract-commit',['env','-u','GIT_AUTHOR_DATE','-u','GIT_COMMITTER_DATE','git','-C',P,'commit','-m','docs: freeze typed fact phases and complete legacy vocabulary mapping'])==0
assert record('g20-final-contract-commit-identity',['git','--no-optional-locks','-C',P,'show','--no-patch','--format=fuller','HEAD'])==0
# New immutable output rather than replacing the earlier successful readonly receipt.
s=(E/'final_readonly_audit.py').read_text().replace("'g20-final-","'g20-terminal-").replace("E/'FINAL_SOURCE_AND_HISTORY_RECEIPT.json'","E/'TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json'")
(E/'terminal_readonly_audit.py').write_text(s)
print('FINAL_TYPED_CONTRACTS_COMMITTED')
