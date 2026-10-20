from pathlib import Path
import json,xml.etree.ElementTree as ET,csv,collections,hashlib
E=Path(__file__).parent;P=E/'worktree';old=E.parent/'G21-20261015T152946Z-354ffd0684'
def cases(p):
 root=ET.parse(p).getroot();out=[]
 for c in root.iter('testcase'):
  out.append(dict(classname=c.get('classname'),name=c.get('name'),outcome='FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'))
 return out
checks={};delta=[]
for label,expected,oldpath,newpath in [('inherited',1897,old/'05_regression/inherited-acceptance/JUNIT.xml',E/'06_regression/inherited-1897-final/JUNIT.xml'),('gen2',108,old/'05_regression/gen2-acceptance-final/JUNIT.xml',E/'06_regression/gen2-108-acceptance/JUNIT.xml')]:
 before=cases(oldpath);after=cases(newpath);a=collections.Counter((c['classname'],c['name']) for c in before);b=collections.Counter((c['classname'],c['name']) for c in after)
 r=dict(original=len(before),current=len(after),missing=list((a-b).elements()),extra=list((b-a).elements()),duplicate=[k for k,v in b.items() if v!=1],nonpass=[c for c in after if c['outcome']!='PASS'],original_junit_sha256=hashlib.sha256(oldpath.read_bytes()).hexdigest(),current_junit_sha256=hashlib.sha256(newpath.read_bytes()).hexdigest())
 assert r['original']==r['current']==expected and not any(r[k] for k in ['missing','extra','duplicate','nonpass']);checks[label]=r
 delta += [dict(group=label,classname=c['classname'],name=c['name'],status='PRESERVED_PASS') for c in after]
newpath=E/'06_regression/acceptance-host-58/JUNIT.xml'
if newpath.exists():
 new=cases(newpath);assert len(new)==58 and all(c['outcome']=='PASS' for c in new);assert len({(c['classname'],c['name']) for c in new})==58
 checks['g22']=dict(current=58,nonpass=[],duplicate=[],junit_sha256=hashlib.sha256(newpath.read_bytes()).hexdigest())
 delta += [dict(group='G22_NEW',classname=c['classname'],name=c['name'],status=c['outcome']) for c in new]
(E/'reports/TEST_IDENTITY_CHECK.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
with (E/'reports/G22_TEST_IDENTITY_DELTA.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=['group','classname','name','status']);w.writeheader();w.writerows(delta)
failures=[]
for f in sorted((E/'commands').glob('*/receipt.json')):
 r=json.loads(f.read_text())
 if r['exit']!=0:failures.append(dict(command=f.parent.name,receipt=str(f.relative_to(E)),exit=r['exit'],stdout=str((f.parent/'stdout.log').relative_to(E)),stderr=str((f.parent/'stderr.log').relative_to(E)),source_provenance='Per-command source epochs/checkpoints where collected; exact initial prototype file bytes UNAVAILABLE before first source snapshot'))
for f in sorted(E.glob('host-*.xml')):
 cc=cases(f);bad=[c for c in cc if c['outcome']!='PASS']
 if bad:failures.append(dict(junit=str(f.relative_to(E)),total=len(cc),failed=bad))
(E/'reports/G22_FAILURE_LEDGER.json').write_text(json.dumps(dict(first_failures_preserved=True,events=failures,source_snapshot_limit='First two constructor/prototype failures predate automatic source byte snapshots; raw original JUnit/command errors retained. Critical label/type/scope red counterexamples include exact source copies.',known_rpo_failure='Original DB-stop test lost unsaved staged nodes at last-SAVE RPO, recovery failed closed; saved-outage control is separate and passes'),ensure_ascii=False,indent=2))
print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk in ('original','current','missing','extra','duplicate','nonpass')} for k,v in checks.items()}))
