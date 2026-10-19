from audit import *
import xml.etree.ElementTree as ET,collections
out=E/'03_regression'
def ids(p):
 cases=list(ET.parse(p).iter('testcase'))
 return cases,collections.Counter(c.get('classname','')+'::'+c.get('name','') for c in cases)
old,prior=ids(E/'00_baseline/V5C_RAW_JUNIT.xml');cases,current=ids(out/'RAW_JUNIT.xml');known=json.loads((E/'00_baseline/V5C_REGRESSION_IDENTITY.json').read_text())
assert len(old)==1868 and len(cases)==1897
assert len(known['new_ids'])==32 and len(set(known['new_ids']))==32
assert set(known['new_ids'])<=set(prior) and set(known['new_ids'])<=set(current)
assert len(set(prior)-set(known['new_ids']))==1836
assert not (prior-current) and len(current-prior)==29 and all(v==1 for v in current.values())
assert not any(c.find(tag) is not None for c in cases for tag in ['failure','error','skipped'])
assert json.loads((E/'commands/g3-regression-final/receipt.json').read_text())['exit_code']==0
assert json.loads((out/'final/RUNTIME_SOURCE_EPOCH.json').read_text())['unchanged'] is True
write(out/'STRICT_IDENTITY_RECHECK.json',{'status':'PASS','at':now(),'original1836':1836,'v5c_additions':32,'new_additions':29,'total':1897,'missing':[],'duplicate':[],'failure_error_skip':[],'junit_sha256':sha(out/'RAW_JUNIT.xml'),'all_assertions_executed':True,'purpose':'Independent explicit identity cross-check; no normalization or redundant conditional assertion'})
print('STRICT_IDENTITY_PASS_1836_PLUS_32_PLUS_29')
