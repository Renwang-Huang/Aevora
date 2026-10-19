from audit import *
import shutil
build=E/'final/approved-build';spec=json.loads((build/'PUBLIC_SELECTION.json').read_text());stage=E/'final/PUBLIC_STAGING';stage.mkdir(mode=0o755)
for rel,row in sorted(spec['files'].items()):
 s=build/'source'/rel;assert not s.is_symlink() and sha(s)==row['sha256'];q=stage/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,q);q.chmod(0o644)
assert set(str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file())==set(spec['files'])
cmds=[('safe-public-git-init',['git','init','-b','main']),('safe-public-git-stage',['git','add','--',*sorted(spec['files'])]),('safe-public-git-commit',['git','-c','user.name=Aevora Release','-c','user.email=release@aevora.invalid','-c','commit.gpgsign=false','commit','-m','release: Aevora Gen2 public release candidate; explicit product-only export']),('safe-public-rc-tag',['git','tag','aevora-gen2-rc1'])]
for label,args in cmds:
 if record(label,args,cwd=stage):raise RuntimeError(label)
clone=E/'final/CLEAN_CLONE';assert record('safe-independent-local-clone',['git','-c','core.hooksPath=/dev/null','clone','--no-hardlinks',stage,clone])==0
assert not (clone/'.git/objects/info/alternates').exists()
identity={n:subprocess.check_output(['git','rev-parse',v],cwd=stage,text=True).strip() for n,v in [('commit','HEAD'),('tree','HEAD^{tree}')]}
identity.update(source_commit=json.loads((E/'RELEASE_SOURCE_FREEZE.json').read_text())['commit'],files=len(spec['files']),stage=str(stage),clone=str(clone),tag='aevora-gen2-rc1',remote_push=False)
write(E/'final/PUBLIC_GIT_RECEIPT.json',identity);print(json.dumps(identity))
secret='/home/PRIVATE_MAINTAINER/.config/aevora/final-6312c046/public-safe'
env=dict(os.environ,AEVORA_IMAGE='aevora-gen2:6312c046-safe-rc1')
raise SystemExit(record('safe-public-clean-install',['python3','scripts/aevora_public_demo.py','start','--project','aevora-safe-6312c046','--secret-dir',secret,'--db-port','19082','--console-port','19084'],cwd=clone,env=env))
