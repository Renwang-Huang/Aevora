"""Owned C0 environment preparation; original repository and archives are read-only."""
from audit import *
import shutil, stat, uuid
old=Path(C['old_full']);P=E/'owned_runtime/source'
def run(label,args):
 code=record(label,args)
 if code:raise RuntimeError(label+' failed')
 return (E/'commands'/label/'stdout.log').read_text().strip()
assert run('c0-active-head',['git','-C',W,'rev-parse','HEAD'])==C['baseline_head']
assert run('c0-active-tree',['git','-C',W,'rev-parse','HEAD^{tree}'])==C['baseline_tree']
assert not run('c0-active-status',['git','-C',W,'status','--porcelain=v1'])
branch=run('c0-active-branch',['git','-C',W,'branch','--show-current'])
run('c0-active-remotes',['git','-C',W,'remote','-v'])
base=json.loads((G5/'g5/ACTIVE_SOURCE_IDENTITY.json').read_text())['source547_sha256']
assert len(base)==547 and all(sha(W/n)==h for n,h in base.items())
sup=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_review_exports/PREGEN2-V5-SUPPLEMENT-20261014T153250Z-e415408795')
receipt=json.loads((sup/'DELIVERY_RECEIPT.json').read_text())
assert sha(Path(receipt['upload_zip']))==receipt['upload_zip_sha256']
assert sha(old/'private_full/FULL_MANIFEST.sha256')==receipt['old_full_manifest_sha256']
assert sha(old/'private_full/FULL_MANIFEST.json')==receipt['old_full_manifest_json_sha256']
write(E/'00_environment/BASELINE_IDENTITY.json',{'at':now(),'head':C['head'],'tree':C['tree'],'branch':branch,'clean':True,'source547_sha256':base,'source_definition':'547 G5-declared paths, not 547 executable modules','supplement_zip_sha256':receipt['upload_zip_sha256'],'old_full_manifest_sha256':receipt['old_full_manifest_sha256'],'old_full_manifest_json_sha256':receipt['old_full_manifest_json_sha256'],'independent_review_document':'PENDING_LOCATE; no claim of reading unavailable document'})
run('c0-isolated-clone',['git','clone','--no-hardlinks',W,P])
run('c0-isolated-branch',['git','-C',P,'switch','-c','v5-closure/'+E.name,C['head']])
run('c0-isolated-no-push',['git','-C',P,'remote','set-url','--push','origin','DISABLED-NO-PUSH'])
run('c0-isolated-status',['git','-C',P,'status','--porcelain=v1'])
assert all(sha(P/n)==h for n,h in base.items())
for n in ['usr','native']:
 q=E/'owned_runtime'/n
 shutil.copytree(old/'owned_runtime'/n,q,symlinks=True)
 assert all(sha(x)==sha(old/'owned_runtime'/n/x.relative_to(q)) and x.stat().st_ino!=(old/'owned_runtime'/n/x.relative_to(q)).stat().st_ino for x in q.rglob('*') if x.is_file() and not x.is_symlink())
write(E/'00_environment/OWNED_TOOLCHAIN_COPY.json',{'at':now(),'ordinary_file_bytes_equal':True,'ordinary_file_inodes_independent':True,'usr_source_label':'OLD_FULL/owned_runtime/usr','native_source_label':'OLD_FULL/owned_runtime/native','no_original_writes':True})
oldcfg=json.loads((old/'RUNTIME_CONFIG.json').read_text());cfg=dict(oldcfg)
cfg.update({'runtime':str(E/'owned_runtime/usr'),'venv':str(E/'owned_runtime/venv'),'container':'aevora-v5c-'+E.name.split('-')[-1],'port':17707,'graph':'aevora_v5c_legacy_'+uuid.uuid4().hex})
# Secrets/DB bootstrap is a separate step; preserve only paths here, no values.
cfg.pop('password_file');cfg.pop('configuration_file')
write(E/'RUNTIME_PRECONFIG.json',cfg)
run('c0-owned-python-version',['bwrap','--die-with-parent','--unshare-user','--unshare-pid','--ro-bind',cfg['runtime'],'/usr','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(E),str(E),'/usr/bin/python3.12','--version'])
run('c0-owned-venv',['bwrap','--die-with-parent','--unshare-user','--unshare-pid','--ro-bind',cfg['runtime'],'/usr','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(E),str(E),'/usr/bin/python3.12','-m','venv',cfg['venv']])
print('C0_COPY_READY',E,flush=True)
