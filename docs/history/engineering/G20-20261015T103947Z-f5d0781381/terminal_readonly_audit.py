from audit import *
import json,stat,hashlib
old=BASE.parents[1];D=P/'docs/gen2/g20'
def git(p,*a):return subprocess.check_output(['git','--no-optional-locks','-C',str(p),*a],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True).strip()
for label,root,args in [
 ('g20-terminal-main-status',W,['status','--short','--branch']),('g20-terminal-main-branches',W,['branch','-avv']),('g20-terminal-main-remotes',W,['remote','-v']),
 ('g20-terminal-base-status',BASE,['status','--short','--branch']),('g20-terminal-base-branches',BASE,['branch','-avv']),('g20-terminal-base-remotes',BASE,['remote','-v']),
 ('g20-terminal-base-object',BASE,['cat-file','-t',C['base_head']]),('g20-terminal-new-status',P,['status','--short','--branch']),('g20-terminal-new-remotes',P,['remote','-v']),('g20-terminal-new-worktree-registry',P,['worktree','list','--porcelain']),('g20-terminal-docs-diff-stat',P,['diff','--stat',C['base_head'],'HEAD']),('g20-terminal-docs-diff-whitespace',P,['diff','--check',C['base_head'],'HEAD'])]:
 assert record(label,['git','--no-optional-locks','-C',root,*args])==0
base=json.loads((old/'00_baseline/BASELINE_IDENTITY.json').read_text())['source547_sha256'];pin=json.loads((old/'source/SOURCE_TRUST_MANIFEST.json').read_text())['files']
assert not git(W,'status','--porcelain=v1') and not git(BASE,'status','--porcelain=v1') and not git(P,'status','--porcelain=v1')
assert all(sha(W/n)==h for n,h in base.items()) and len(base)==547
assert all(sha(BASE/n.removeprefix('frozen_source_snapshot/'))==h and sha(P/n.removeprefix('frozen_source_snapshot/'))==h for n,h in pin.items()) and len(pin)==551
new=git(P,'diff','--name-only',C['base_head'],'HEAD').splitlines();assert len(new)==49 and all(n.startswith('docs/gen2/g20/') for n in new)
freeze=json.loads((D/'CONTRACT_FREEZE_INDEX.json').read_text());assert set(freeze['files'])|{'CONTRACT_FREEZE_INDEX.json'}=={str(p.relative_to(D)) for p in D.rglob('*') if p.is_file()}
assert all(sha(D/n)==v['sha256'] and (D/n).stat().st_size==v['bytes'] for n,v in freeze['files'].items())
# No shared object inode/alternates with the sealed original Git object store.
common=Path(git(P,'rev-parse','--path-format=absolute','--git-common-dir'));original=Path(git(BASE,'rev-parse','--path-format=absolute','--git-common-dir'));matches=0
assert common==Path(C['git_common']) and not (common/'objects/info/alternates').exists()
for p in (common/'objects').rglob('*'):
 if p.is_file():
  q=original/'objects'/p.relative_to(common/'objects')
  if q.is_file():assert (p.stat().st_dev,p.stat().st_ino)!=(q.stat().st_dev,q.stat().st_ino) and sha(p)==sha(q);matches+=1
assert matches>0
# The old terminal manifest pins the old sealed Full manifest, ZIP and derived outputs.
oldexport=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_review_exports')/old.name
m=json.loads((oldexport/'DELIVERY_MANIFEST.json').read_text());assert len(m['files'])==84
assert all(Path(d['absolute_path']).stat().st_size==d['bytes'] and sha(Path(d['absolute_path']))==d['sha256'] for d in m['files'].values())
# Full old metadata+bytes recheck: exclude only its predeclared self/derived boundaries.
f=json.loads((old/'private_full/FULL_MANIFEST.json').read_text());old_count=0
for n,d in f['files'].items():
 p=old/n;s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_size==d['bytes'] and s.st_mtime_ns==d['mtime_ns'] and oct(s.st_mode&0o7777)==d['mode'] and sha(p)==d['sha256'];old_count+=1
for d in f['links']:
 p=old/d['path'];assert p.is_symlink() and os.readlink(p)==d['target'] and oct(p.lstat().st_mode&0o7777)==d['mode']
owned=subprocess.check_output(['docker','ps','-aq','--filter','label=aevora.owner='+C['id']],text=True).strip();assert not owned
receipt={'status':'PASS_READONLY_SOURCE_HISTORY_FREEZE_AND_RESOURCE_AUDIT','at':now(),'main_head':git(W,'rev-parse','HEAD'),'main_tree':git(W,'rev-parse','HEAD^{tree}'),'main547_verified':len(base),'main_clean':True,'v5c1_551_verified':len(pin),'v5c1_clean':True,'new_head':git(P,'rev-parse','HEAD'),'new_tree':git(P,'rev-parse','HEAD^{tree}'),'new_parent':git(P,'rev-parse','HEAD^'),'new_branch':git(P,'branch','--show-current'),'new_clean':True,'new_files':49,'changes_outside_design':[],'production_source_changes':0,'independent_common_git':str(common),'common_objects_bytes_equal_but_inodes_distinct':matches,'historical_v5c1_full_files_rehashed':old_count,'historical_v5c1_full_links_verified':len(f['links']),'historical_v5c1_terminal_files_rehashed':84,'old_full_manifest_sha256':sha(old/'private_full/FULL_MANIFEST.json'),'freeze_index_sha256':sha(D/'CONTRACT_FREEZE_INDEX.json'),'owned_probe_containers_remaining':0,'new_model_challenges':0,'inherited1897_rerun':False,'push_or_baseline_merge':False}
write(E/'TERMINAL_SOURCE_AND_HISTORY_RECEIPT.json',receipt)
print(json.dumps(receipt))
