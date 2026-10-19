from audit import *
import sys
import xml.etree.ElementTree as ET
old=E.parent/'G23-20261016T021142Z-1e5e8e1af0/10_regression_final'
def ids(p,pass_required=True):
 rows=ET.parse(p).findall('.//testcase');identities={(r.get('classname'),r.get('name')) for r in rows};assert len(rows)==len(identities),p
 if pass_required:assert all(not any(c.tag in {'failure','error','skipped'} for c in r) for r in rows),p
 return identities

def check(current):
 jobs=[('inherited-1897','inherited-1897',1897),('graph-v2-108','gen2-108',108),('host58-native46','host58-new46',104)]
 all_current=set();all_old=set();rows=[]
 for new,prior,count in jobs:
  p=current/new/'JUNIT.xml';a=ids(p);b=ids(old/prior/'JUNIT.xml');assert len(a)==count and a==b,(new,len(a),len(b))
  assert not all_current&a;all_current|=a;all_old|=b;rows.append(dict(suite=new,tests=count,current_sha256=sha(p),old_sha256=sha(old/prior/'JUNIT.xml'),exact_identity_match=True))
 assert len(all_current)==2109 and all_old==all_current
 assert ids(current/'CONTRACT86.xml')==ids(old/'CONTRACT86.xml') and len(ids(current/'CONTRACT86.xml'))==86
 result=dict(status='PASS',at=now(),inherited_developer_tests=2109,contracts=86,suites=rows,no_missing=True,no_extra=True,no_failure_error_skip=True,source='This run XML identities compared to read-only G23 final XML; historical hashes identify original bytes, not a new model run.')
 write(current/'EXACT_IDENTITY_RECEIPT.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else E/'07_frozen_regression')
