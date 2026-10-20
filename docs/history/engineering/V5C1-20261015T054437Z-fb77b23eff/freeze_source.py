from audit import *
import subprocess,shutil
P=Path(C['worktree'])
names=['aevora_core/src/aevora/mcp_server.py','aevora_core/src/aevora/mcp_projection.py','aevora_core/tests/test_v5c1_bounded_transport.py','aevora_core/docs/MCP_BOUNDED_EVIDENCE.md']
assert record('g2-stage-exact-paths',['git','-C',P,'add',*names])==0
assert record('g2-patch-commit',['git','-C',P,'commit','-m','Bound public MCP evidence to authorized immutable pages'])==0
head=subprocess.check_output(['git','-C',str(P),'rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','-C',str(P),'rev-parse','HEAD^{tree}'],text=True).strip();parent=subprocess.check_output(['git','-C',str(P),'rev-parse','HEAD^'],text=True).strip();assert parent==C['head']
assert not subprocess.check_output(['git','-C',str(P),'status','--porcelain=v1'])
patch=subprocess.check_output(['git','-C',str(P),'diff','--binary',parent,head]);(E/'02_fix/patch.diff').write_bytes(patch)
old=json.loads((E/'00_baseline/BASELINE_IDENTITY.json').read_text())['source547_sha256']
assert all(sha(P/n)==h for n,h in old.items() if n.startswith(('app/','benchmark/','evaluator/')))
allfiles=subprocess.check_output(['git','-C',str(P),'ls-files','-z']).decode().split('\0');allfiles=[p for p in allfiles if p]
source=E/'source';snapshot=source/'frozen_source_snapshot';snapshot.mkdir(parents=True);files={}
for n in allfiles:
 q=snapshot/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/n,q);files['frozen_source_snapshot/'+n]=sha(q)
write(source/'SOURCE_TRUST_MANIFEST.json',{'files':files,'source_commit':head,'source_tree':tree,'created_at':now(),'authority':'TRUSTED_LOCAL_PIN; not external attestation','kind':'V5C1_CURRENT_PATCH_TREE'})
write(E/'02_fix/PATCH_FREEZE.json',{'at':now(),'base':C['head'],'parent':parent,'commit':head,'tree':tree,'changed_paths':names,'patch_sha256':sha(E/'02_fix/patch.diff'),'source_manifest_sha256':sha(source/'SOURCE_TRUST_MANIFEST.json'),'source_snapshot_files':len(files),'original_business_runner_oracle_bytes_unchanged':True,'baseline_547_main_unchanged':all(sha(W/n)==h for n,h in old.items()),'local_only':True})
print('SOURCE_FROZEN',head,tree,len(files),flush=True)
