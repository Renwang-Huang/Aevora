from audit import *
import subprocess
P=Path(C['worktree'])
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
base=json.loads((E/'00_baseline/BASELINE_IDENTITY.json').read_text())['source547_sha256'];pin=json.loads((E/'source/SOURCE_TRUST_MANIFEST.json').read_text());patch=json.loads((E/'02_fix/PATCH_FREEZE.json').read_text())
assert git(W,'rev-parse','HEAD')==C['baseline_head'] and git(W,'rev-parse','HEAD^{tree}')==C['baseline_tree'] and not git(W,'status','--porcelain=v1') and all(sha(W/n)==h for n,h in base.items())
assert git(P,'rev-parse','HEAD')==patch['commit'] and git(P,'rev-parse','HEAD^{tree}')==patch['tree'] and not git(P,'status','--porcelain=v1') and all(sha(P/n.removeprefix('frozen_source_snapshot/'))==h for n,h in pin['files'].items())
changed=git(P,'diff','--name-only',C['head'],'HEAD').splitlines();assert sorted(changed)==sorted(patch['changed_paths'])
protected=[n for n in base if n.startswith(('app/','benchmark/','evaluator/'))];assert all(sha(P/n)==base[n] for n in protected)
common=Path(git(P,'rev-parse','--path-format=absolute','--git-common-dir'));assert common.resolve()==Path(C['git_common']).resolve() and not (common/'objects/info/alternates').exists()
assert record('g6-new-git-object-fsck',['git','--git-dir',common,'fsck','--full','--no-reflogs','--no-progress'])==0
assert record('g6-new-worktree-registry',['git','--git-dir',common,'worktree','list','--porcelain'])==0
model=[]
for phase in ['S1','S2']:
 s=json.loads((E/'04_live'/phase/'ORIGINAL_RUN_SUMMARY.json').read_text());m=json.loads((E/'04_live'/phase/'runs'/s['run_id']/'runtime_metadata.json').read_text());b=m['model_broker'];assert b['token_revoked'] and b['socket_unlinked'] and b['handler_cleanup_complete'] and b['active_requests']==0;model.append({'phase':phase,'model_token_revoked':b['token_revoked'],'model_socket_unlinked':b['socket_unlinked'],'handler_cleanup_complete':b['handler_cleanup_complete'],'active_requests':b['active_requests']})
write(E/'06_audit/FINAL_SOURCE_IDENTITY.json',{'status':'PASS','at':now(),'main_head':git(W,'rev-parse','HEAD'),'main_tree':git(W,'rev-parse','HEAD^{tree}'),'main_branch':git(W,'branch','--show-current'),'main_clean':True,'main_remotes':git(W,'remote','-v'),'baseline_paths_verified':len(base),'patch_head':patch['commit'],'patch_tree':patch['tree'],'patch_parent':C['head'],'patch_clean':True,'patch_paths_verified':len(pin['files']),'changed_paths':changed,'business_runner_oracle_paths_verified_unchanged':len(protected),'new_git_common_dir':str(common),'objects_alternates_absent':True,'local_worktree_is_new_owned_registry':True,'model_channel_cleanup':model,'frozen_baseline_merged':False,'remote_push_executed':False,'gen2_features_started':False})
print('FINAL_SOURCE_IDENTITY_PASS_547_551_CLEAN')
