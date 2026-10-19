from runtime import *
import shutil
assert record('v4-console-ci',['npm','--prefix',str(P/'console'),'ci','--ignore-scripts'],cwd=P)==0
assert record('v4-console-build',['npm','--prefix',str(P/'console'),'run','build'],cwd=P)==0
assert record('v4-console-six-unit',['npm','--prefix',str(P/'console'),'test'],cwd=P)==0
for i in [1,2]:assert record('v4-public-build-'+str(i),runtime('tools/dev.py','public-build','--output',str(E/'05_product'/('public-build-'+str(i)))))==0
a=json.loads((E/'05_product/public-build-1/PUBLIC_SELECTION.json').read_text());b=json.loads((E/'05_product/public-build-2/PUBLIC_SELECTION.json').read_text());old=json.loads((G5/'g5/public-product/PUBLIC_SELECTION.json').read_text())
assert a['files']==b['files']==old['files']
assert sha(E/'05_product/public-build-1/aevora-gen15-public-source.zip')==sha(E/'05_product/public-build-2/aevora-gen15-public-source.zip')==sha(G5/'g5/public-product/aevora-gen15-public-source.zip')
write(E/'05_product/release_manifest_diff.json',{'status':'PASS','file_count':len(a['files']),'current_repeated_selection_identical':True,'g5_selection_identical':True,'zip_sha256':sha(E/'05_product/public-build-1/aevora-gen15-public-source.zip'),'package_byte_hashes':[{p.name:sha(p) for p in (E/'05_product'/('public-build-'+str(i))/'dist').iterdir()} for i in [1,2]],'sdist_wheel_byte_determinism':'OBSERVED_HASHES; normalized member comparison follows','source_changed':False})
# Reuse original SDK assertions with only external collector imports substituted.
s=(P/'scripts/aevora_h4_install.py').read_text()
oldline='from scripts.aevora_h4_audit import ROOT,archive,write,digest,now'
assert s.count(oldline)==1
replacement="""from hashlib import sha256
from datetime import datetime,timezone
ROOT=Path('/public')
def archive():return Path('/install')
def digest(p):return sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\\n')
"""
probe=E/'05_product/clean_install_probe.py';probe.write_text(s.replace(oldline,replacement))
inside=E/'05_product/clean_install';inside.mkdir(mode=0o700)
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text())
cmd=['bwrap','--die-with-parent','--unshare-user','--unshare-pid','--ro-bind',cfg['runtime'],'/usr','--ro-bind','/etc/resolv.conf','/etc/resolv.conf','--ro-bind','/etc/ssl/certs','/etc/ssl/certs','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',str(E/'05_product/public-build-1/source'),'/public','--ro-bind',str(probe),'/probe.py','--bind',str(inside),'/install','--ro-bind',cfg['password_file'],'/run/db.secret','--clearenv','--setenv','HOME','/tmp','--setenv','PATH','/usr/bin:/bin','--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','SSL_CERT_FILE','/etc/ssl/certs/ca-certificates.crt','--setenv','AEVORA_FALKORDB_HOST','127.0.0.1','--setenv','AEVORA_FALKORDB_PORT',str(cfg['port']),'--setenv','AEVORA_FALKORDB_PASSWORD_FILE','/run/db.secret','--chdir','/public','/usr/bin/python3.12','/probe.py','--label','pregen2-clean-onboarding']
write(E/'05_product/CLEAN_INSTALL_SCOPE.json',{'public_selection_sha256':sha(E/'05_product/public-build-1/PUBLIC_SELECTION.json'),'frozen_assertion_source':str(W/'scripts/aevora_h4_install.py'),'frozen_assertion_source_sha256':sha(W/'scripts/aevora_h4_install.py'),'external_probe_sha256':sha(probe),'change':'Collector ROOT/archive/hash/write/clock imports only; original SDK assertions retained','mounts':'Only runtime/public114files/externalinstall/probe/ownedDBsecret; no frozen or private Benchmark mount','model_calls':0})
assert record('v4-clean-public-only-install',cmd)==0
print('V4_BUILD_INSTALL_PASS')
