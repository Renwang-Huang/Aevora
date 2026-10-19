from audit import *
import json,xml.etree.ElementTree as ET,shutil
D=P/'docs/gen2/g20';index=D/'CONTRACT_FREEZE_INDEX.json';shutil.copyfile(index,E/'source_audit/CONTRACT_FREEZE_INDEX.first_commit.json')
cs=list(ET.parse(E/'checks/post-normalization/JUNIT.xml').getroot().iter('testcase'));assert len(cs)==54 and all(not list(c) for c in cs)
prior=subprocess.check_output(['git','-C',str(P),'rev-parse','HEAD'],text=True).strip()
x=json.loads(index.read_text());x.update(created_at=now(),supersedes_design_commit=prior,changes_since_first_freeze='CSV CRLF→LF only; same semantic rows; prior commit/failure retained')
x['files']={str(p.relative_to(D)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(D.rglob('*')) if p.is_file() and p.name!='CONTRACT_FREEZE_INDEX.json'}
x['current_design_checks']['junit_sha256']=sha(E/'checks/post-normalization/JUNIT.xml')
index.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
assert record('g20-stage-normalized-design',['git','-C',P,'add','--','docs/gen2/g20'])==0
assert record('g20-normalized-diff-check',['git','-C',P,'diff','--cached','--check'])==0
assert record('g20-normalized-commit',['env','-u','GIT_AUTHOR_DATE','-u','GIT_COMMITTER_DATE','git','-C',P,'commit','-m','docs: normalize Gen2 contract matrices and refresh freeze index'])==0
assert record('g20-final-git-identity',['git','--no-optional-locks','-C',P,'show','--no-patch','--format=fuller','HEAD'])==0
print('FINAL_G20_DESIGN_COMMIT_CREATED')
