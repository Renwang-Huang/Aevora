from audit import *
import shutil,socket,uuid,secrets
O=Path(C['old_full']); S=O/'owned_runtime/source'; P=Path(C['worktree'])
def run(label,args):
 assert record(label,args)==0,label
 return (E/'commands'/label/'stdout.log').read_text().strip()
head=run('g0-active-head',['git','-C',W,'rev-parse','HEAD']);assert head==C['baseline_head']
tree=run('g0-active-tree',['git','-C',W,'rev-parse','HEAD^{tree}']);assert tree==C['baseline_tree']
assert not run('g0-active-status',['git','-C',W,'status','--porcelain=v1'])
branch=run('g0-active-branch',['git','-C',W,'branch','--show-current'])
run('g0-active-remotes',['git','-C',W,'remote','-v'])
main_object=record('g0-active-v5c-object',['git','-C',W,'cat-file','-t',C['head']])
assert run('g0-v5c-head',['git','-C',S,'rev-parse','HEAD'])==C['head']
assert run('g0-v5c-tree',['git','-C',S,'rev-parse','HEAD^{tree}'])==C['tree']
assert not run('g0-v5c-status',['git','-C',S,'status','--porcelain=v1'])
run('g0-v5c-ancestor',['git','-C',S,'merge-base','--is-ancestor',head,C['head']])
run('g0-v5c-diff',['git','-C',S,'diff','--binary',head,C['head']])
base=json.loads((G5/'g5/ACTIVE_SOURCE_IDENTITY.json').read_text())['source547_sha256']
assert len(base)==547 and all(sha(W/n)==h for n,h in base.items())
assert sha(O/'private_full/FULL_MANIFEST.json')=='c02d55b95e074a6b301c5788604e52918bf5e92beac41fa886bff6f20d7e6ab7'
manifest=json.loads((O/'private_full/FULL_MANIFEST.json').read_text())
for name in ['owned_db_data/dump.rdb','03_feedback/s2_outcome/graph_after.json','06_regression/attempt1/JUNIT.xml']:
 assert sha(O/name)==manifest['files'][name]['sha256'],name
write(E/'00_baseline/BASELINE_IDENTITY.json',{'at':now(),'head':head,'tree':tree,'branch':branch,'clean':True,'source547_sha256':base,'v5c_head':C['head'],'v5c_tree':C['tree'],'v5c_source':str(S),'v5c_ancestor_verified':True,'v5c_object_in_main_exit':main_object,'old_full_manifest_sha256':sha(O/'private_full/FULL_MANIFEST.json'),'old_full_manifest_link_sha256':sha(O/'private_full/FULL_MANIFEST.sha256'),'independent_reviews':'UNAVAILABLE: exact two filenames not found; taskbook permits Full/source fallback'})
assert not Path(C['git_common']).exists() and not P.exists()
run('g0-independent-git-clone',['git','clone','--bare','--no-hardlinks',S,C['git_common']])
run('g0-no-push',['git','--git-dir',C['git_common'],'remote','set-url','--push','origin','DISABLED-NO-PUSH'])
run('g0-worktree',['git','--git-dir',C['git_common'],'worktree','add','-b',C['branch'],P,C['head']])
run('g0-worktree-identity',['git','-C',P,'status','--short','--branch'])
changed=set(run('g0-v5c-paths',['git','-C',P,'diff','--name-only',head,C['head']]).splitlines())
assert changed=={'aevora_core/src/aevora/mcp_server.py','integrations/codex_agent.py','aevora_core/tests/test_v5c_context_contract.py'}
assert all(sha(P/n)==sha(S/n) for n in base)
for name in ['usr','native']:
 q=E/'owned_runtime'/name;shutil.copytree(O/'owned_runtime'/name,q,symlinks=True)
 files=[x for x in q.rglob('*') if x.is_file() and not x.is_symlink()]
 assert all(sha(x)==sha(O/'owned_runtime'/name/x.relative_to(q)) and x.stat().st_ino!=(O/'owned_runtime'/name/x.relative_to(q)).stat().st_ino for x in files)
 write(E/'00_baseline'/('TOOLCHAIN_'+name+'.json'),{'source':str(O/'owned_runtime'/name),'files':len(files),'all_bytes_equal':True,'all_inodes_independent':True})
cfg=json.loads((O/'RUNTIME_CONFIG.json').read_text());cfg.update(runtime=str(E/'owned_runtime/usr'),venv=str(E/'owned_runtime/venv'),container='aevora-v5c1-'+E.name.split('-')[-1],port=17717,graph='aevora_v5c1_regression_'+uuid.uuid4().hex)
s=socket.socket();s.bind(('127.0.0.1',cfg['port']));s.close()
private=Path('/home/PRIVATE_MAINTAINER/.config/aevora')/('v5c1-'+uuid.uuid4().hex);private.mkdir(mode=0o700)
key=private/'falkordb.password';key.write_text(secrets.token_urlsafe(32)+'\n');key.chmod(0o600)
conf=private/'falkordb.conf';conf.write_text('bind 0.0.0.0\nprotected-mode yes\nport 6379\nrequirepass '+key.read_text().strip()+'\ndir /data\ndbfilename dump.rdb\nsave ""\nappendonly no\n');conf.chmod(0o600)
cfg.update(password_file=str(key),configuration_file=str(conf));write(E/'RUNTIME_CONFIG.json',cfg)
data=E/'owned_db_data';data.mkdir(mode=0o700);shutil.copy2(O/'owned_db_data/dump.rdb',data/'dump.rdb');assert sha(data/'dump.rdb')==sha(O/'owned_db_data/dump.rdb') and (data/'dump.rdb').stat().st_ino!=(O/'owned_db_data/dump.rdb').stat().st_ino
write(E/'00_baseline/RDB_COPY.json',{'source_sha256':sha(O/'owned_db_data/dump.rdb'),'copy_sha256':sha(data/'dump.rdb'),'bytes':(data/'dump.rdb').stat().st_size,'independent_inode':True,'old_manifest_match':True,'restoration_scope':'COMPLETE_SAVED_RDB_NO_EDGE_REMOVAL'})
write(E/'00_baseline/SECRETS_METADATA.json',{'external_directory':str(private),'directory_mode':oct(private.stat().st_mode&0o777),'file_modes':[oct(p.stat().st_mode&0o777) for p in [key,conf]],'values':'NOT_ARCHIVED','secret_hashes':'NOT_COMPUTED'})
bwrap=['bwrap','--die-with-parent','--unshare-user','--unshare-pid','--ro-bind',cfg['runtime'],'/usr','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(E),str(E)]
run('g0-python-version',bwrap+['/usr/bin/python3.12','--version'])
run('g0-venv',bwrap+['/usr/bin/python3.12','-m','venv',cfg['venv']])
image='falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62'
run('g0-owned-db-start',['docker','run','-d','--name',cfg['container'],'--label','aevora.audit.owner='+E.name,'--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--publish','127.0.0.1:'+str(cfg['port'])+':6379','--memory','1g','--cpus','2','--pids-limit','256','--mount','type=bind,src='+str(conf)+',dst=/run/secrets/server.conf,readonly','--mount','type=bind,src='+str(key)+',dst=/run/secrets/db.password,readonly','--mount','type=bind,src='+str(data)+',dst=/data','--entrypoint','redis-server',image,'--loadmodule','/var/lib/falkordb/bin/falkordb.so','--include','/run/secrets/server.conf','--appendonly','no'])
from runtime import runtime
run('g0-install',runtime('-m','pip','install','-e',P/'aevora_core','-e',P/'console','-e',P,'setuptools==76.1.0','wheel==0.45.1'))
run('g0-pip-check',runtime('-m','pip','check'))
run('g0-package-inventory',runtime('-m','pip','list','--format=json'))
run('g0-dev-help',runtime('tools/dev.py','--help'))
run('g0-db-state',['docker','inspect','--format','{{json .State}}',cfg['container']])
write(E/'00_baseline/G0_BOOTSTRAP.json',{'status':'PASS','at':now(),'worktree':str(P),'git_registry':C['git_common'],'old_git_registry_untouched':True,'owned_port':cfg['port'],'original_graph':'aevora_v5c_live_0a70f0ccc4204a75846e00199c2923c0','next':'Verify full graph and focused authority map before fix'})
