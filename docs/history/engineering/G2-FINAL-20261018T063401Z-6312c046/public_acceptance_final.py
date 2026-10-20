from audit import *
import urllib.request
out=E/'final/acceptance_verified';out.mkdir(exist_ok=False);container='aevora-safe-6312c046-console-1'
checks=[]
def run(label,args):
 code=record(label,args);assert code==0,label;checks.append(dict(name=label,status='PASS'))
inspect="""import sys,sqlite3,json,importlib,importlib.metadata,pkgutil,aevora,aevora_observatory
for n in ['benchmark','evaluator','integrations','aevora_maintainer','app']:
 assert importlib.util.find_spec(n) is None,n
modules=[]
for item in pkgutil.walk_packages(aevora.__path__,'aevora.'):
 if item.name.endswith('.__main__'):continue
 if item.name=='aevora.audit_capsule':
  try:importlib.import_module(item.name)
  except ImportError as e:assert str(e)=='aevora.audit_capsule requires the private MAINTAINER_ONLY distribution'
  else:raise AssertionError('Private maintainer alias must not import successfully')
  continue
 importlib.import_module(item.name);modules.append(item.name)
print(json.dumps(dict(status='PASS',python=sys.version,sqlite=sqlite3.sqlite_version,modules_imported=len(modules),core_path=aevora.__file__,private_packages='ABSENT',packages={n:importlib.metadata.version(n) for n in ['aevora-core','aevora-console','falkordb','redis','mcp','starlette','uvicorn']}),sort_keys=True))
"""
run('verified-safe-install-import-all-core',['docker','exec',container,'python','-I','-c',inspect])
run('verified-safe-install-pip-check',['docker','exec',container,'python','-m','pip','check'])
run('verified-safe-install-test-dependency',['docker','exec',container,'python','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--target','/tmp/aevora-public-test-deps','pytest==9.1.1'])
code="import sys;sys.path.insert(0,'/tmp/aevora-public-test-deps');import pytest;raise SystemExit(pytest.main(['-q','/opt/aevora/aevora_core/public_tests','-p','no:cacheprovider','--junitxml=/tmp/PUBLIC_JUNIT.xml']))"
run('verified-safe-clean-public-unit-tests',['docker','exec',container,'python','-I','-c',code])
run('verified-safe-clean-public-junit-copy',['docker','cp',container+':/tmp/PUBLIC_JUNIT.xml',out/'PUBLIC_JUNIT.xml'])
run('verified-safe-official-mcp-four-tools',['docker','exec',container,'python','-I','/opt/aevora/aevora_core/public_tests/check_live_mcp.py','/state'])
base='http://127.0.0.1:19084';observations=[]
for context,stage,expect in [('threads','before','APPLY'),('workers','before','ABSTAIN'),('unknown','before','VERIFY'),('threads','after','ABSTAIN')]:
 with urllib.request.urlopen(base+'/api/journey?context='+context+'&stage='+stage,timeout=10) as r:data=json.load(r);assert r.status==200
 assert data['recommendation']['core_verdict']==expect and data['query_receipts'] and data['fallback'] is False and data['mode']=='LIVE_SYNTHETIC_DEMO'
 observations.append(dict(context=context,stage=stage,actual=data['recommendation']['core_verdict'],witness_sha256=data['witness_sha256'],query_receipts=len(data['query_receipts'])))
 write(out/(context+'-'+stage+'.json'),data)
checks.append(dict(name='four_actual_graph_observations',status='PASS'))
for service in ['graph','console']:
 data=json.loads(subprocess.check_output(['docker','inspect','aevora-safe-6312c046-'+service+'-1']))[0]
 snapshot=dict(service=service,id=data['Id'],image=data['Image'],created=data['Created'],health=data['State']['Health']['Status'],ports=data['HostConfig']['PortBindings'],memory=data['HostConfig']['Memory'],nano_cpus=data['HostConfig']['NanoCpus'],pids_limit=data['HostConfig']['PidsLimit'],read_only_root=data['HostConfig']['ReadonlyRootfs'],user=data['Config']['User'],mounts=[dict(type=m['Type'],destination=m['Destination'],rw=m['RW']) for m in data['Mounts']])
 assert snapshot['health']=='healthy' and snapshot['read_only_root'] and all(x['HostIp']=='127.0.0.1' for v in snapshot['ports'].values() for x in v);write(out/(service+'-runtime.json'),snapshot)
for name in ['aevora-safe-6312c046_graph-data','aevora-safe-6312c046_demo-state']:
 data=json.loads(subprocess.check_output(['docker','volume','inspect',name]))[0];write(out/(name+'.json'),{k:data[k] for k in ['Name','Driver','CreatedAt','Labels']})
write(out/'CLEAN_INSTALL_RESULT.json',dict(status='PASS',at=now(),checks=checks,observations=observations,public_clone=str(E/'final/CLEAN_CLONE'),project='aevora-safe-6312c046',new_volumes=True,evidence='Docker up logs show Creating/Created volumes; selected immutable public clone only; post-install runtime selected inspect; no private source bind mount.',model_execution=False,private_oracle='NOT_PRESENT',production_host='NOT_EXERCISED'))
print('Independent public clean clone installation, imports, tests and real MCP: PASS')
