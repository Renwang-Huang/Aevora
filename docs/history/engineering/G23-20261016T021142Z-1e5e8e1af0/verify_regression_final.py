from audit import *
import xml.etree.ElementTree as ET,collections,csv
old=E.parent/'G22-20261015T174846Z-88fad40ffd'
pairs=[('inherited1897',old/'06_regression/inherited-1897-final/JUNIT.xml',E/'08_regression_final/inherited-1897/JUNIT.xml',1897),('gen2-108',old/'06_regression/gen2-108-acceptance/JUNIT.xml',E/'08_regression_final/gen2-108/JUNIT.xml',108),('g22-58',old/'06_regression/acceptance-host-58/JUNIT.xml',E/'08_regression_final/host58-exact-root/JUNIT.xml',58)]
def cases(p):return ET.parse(p).findall('.//testcase')
def identity(rows):return collections.Counter((r.attrib.get('classname'),r.attrib.get('name')) for r in rows)
results=[]
for label,previous,current,n in pairs:
 before=identity(cases(previous));all_rows=cases(current);required=[r for r in all_rows if not r.attrib.get('classname','').startswith('tests.g23.')];after=identity(required)
 assert before==after and len(required)==n,label
 assert all(not any(x.tag in {'failure','error','skipped'} for x in r) for r in all_rows)
 assert len(after)==n,label
 results.append(dict(label=label,count=n,identities_equal=True,fail=0,error=0,skip=0,junit_sha256=sha(current),previous_junit_sha256=sha(previous)))
rows=cases(E/'08_regression_final/host58-new45/JUNIT.xml');new=[r for r in rows if r.attrib.get('classname','').startswith('tests.g23.')];assert len(new)==45
contracts=cases(E/'08_regression_final/CONTRACT86.xml');assert len(contracts)==86 and all(not any(x.tag in {'failure','error','skipped'} for x in r) for r in contracts)
write(E/'08_regression_final/EXACT_IDENTITY_RECEIPT.json',{'inherited':2063,'results':results,'new':45,'contracts':86,'new_test_identities':list(identity(new)),'junit_identity_key':['classname','name'],'compared':'unredacted Full bytes; no path aliasing'})
print('EXACT_2063_PLUS45_PLUS86_PASS')
