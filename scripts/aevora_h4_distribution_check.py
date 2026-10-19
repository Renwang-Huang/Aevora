"""Inside public-only image: actual clean wheel/sdist installs and byte provenance."""
import hashlib,importlib.metadata,json,os,platform,sqlite3,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

out=Path('/evidence');out.mkdir(exist_ok=True);commands=[]
def command(argv):
    start=datetime.now(timezone.utc).isoformat();r=subprocess.run(argv,capture_output=True,timeout=300);n=len(commands)+1
    (out/(str(n)+'-stdout.log')).write_bytes(r.stdout);(out/(str(n)+'-stderr.log')).write_bytes(r.stderr)
    row={'argv':argv,'exit_code':r.returncode,'started_at':start,'ended_at':datetime.now(timezone.utc).isoformat(),'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()};commands.append(row);(out/'COMMANDS.json').write_text(json.dumps(commands,indent=2)+'\n')
    if r.returncode:raise RuntimeError('Actual package command failed; stdout/stderr retained')
    return r.stdout
facts={}
for kind,pattern in [('wheel','*.whl'),('sdist','*.tar.gz')]:
    artifacts=sorted(Path('/dist').glob(pattern));assert len(artifacts)==2
    target='/tmp/installed-'+kind
    command([sys.executable,'-m','pip','install','--no-deps','--target',target,*map(str,artifacts)])
    code="import sys;sys.path.insert(0,"+repr(target)+");import importlib.util,json,pathlib,hashlib,aevora,aevora_observatory;assert importlib.util.find_spec('benchmark') is None;assert importlib.util.find_spec('evaluator') is None;assert aevora.__file__.startswith("+repr(target)+");assert aevora_observatory.__file__.startswith("+repr(target)+");print(json.dumps({'core_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path(aevora.__file__).parent.glob('*.py')},'console_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path(aevora_observatory.__file__).parent.glob('*.py')},'prebuilt_frontend':(pathlib.Path(aevora_observatory.__file__).parent/'static/index.html').is_file()}))"
    facts[kind]=json.loads(command([sys.executable,'-I','-c',code]));assert facts[kind]['prebuilt_frontend']
assert facts['wheel']==facts['sdist']
command([sys.executable,'-m','pip','check'])
command([sys.executable,'-I','/opt/aevora/h4/verify_hero.py','/opt/aevora/h4','--sha256','c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776'])
freeze=command([sys.executable,'-m','pip','freeze']);(out/'ACTUAL_DEPENDENCIES.txt').write_bytes(freeze)
result={'status':'PASS','actual_commands':commands,'installed_package_sources':facts,'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'model_calls':0,'scope':'Public-only actual wheel/sdist installation, prebuilt frontend and independently pinned Hero verifier; no Benchmark imports'}
(out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','commands':len(commands),'python':result['python'],'sqlite':result['sqlite']}))
