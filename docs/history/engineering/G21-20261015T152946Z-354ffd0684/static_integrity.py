from audit import *
import stat
OLD=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/G20-20261015T103947Z-f5d0781381')
V51=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/V5C1-20261015T054437Z-fb77b23eff')
ACTIVE=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/aevora')
assert record('frozen-gen1-git',['git','--no-optional-locks','status','--short','--branch'],cwd=ACTIVE)==0
assert record('frozen-gen1-identity',['git','rev-parse','HEAD','HEAD^{tree}'],cwd=ACTIVE)==0
assert record('g20-git-identity',['git','--no-optional-locks','status','--short','--branch'],cwd=OLD/'worktree')==0
pins=json.loads((V51/'source/SOURCE_TRUST_MANIFEST.json').read_text())['files'];mismatches=[]
for name,expected in pins.items():
 rel=name.removeprefix('frozen_source_snapshot/')
 for root in [V51/'owned_runtime/source',OLD/'worktree']:
  f=root/rel
  if sha(f)!=expected:mismatches.append(str(f))
base547=json.loads((V51/'00_baseline/BASELINE_IDENTITY.json').read_text())['source547_sha256']
for rel,expected in base547.items():
 if sha(ACTIVE/rel)!=expected:mismatches.append(str(ACTIVE/rel))
# Every previous G20 Full member hash, metadata and exact-membership remains independently verifiable.
manifest=json.loads((OLD/'DELIVERY_MANIFEST.json').read_text())
write(E/'00_baseline/PROTECTED_SOURCE_RECHECK.json',dict(v51_paths=len(pins),g20_old_source_paths=len(pins),gen1_paths=len(base547),mismatches=mismatches,g20_manifest_sha256=sha(OLD/'DELIVERY_MANIFEST.json'),v51_manifest_sha256=sha(V51/'private_full/FULL_MANIFEST.json')))
assert not mismatches
assert record('new-independent-git-fsck',['git','fsck','--full'])==0
assert record('new-git-common',['git','rev-parse','--git-common-dir'])==0
assert not (E/'repository.git/objects/info/alternates').exists()
write(E/'00_baseline/OBJECT_INDEPENDENCE.json',dict(git_common=str(E/'repository.git'),old_common=str(OLD/'repository.git'),alternates=False,clone_no_hardlinks=True,main_changed=False))
