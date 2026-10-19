from audit import *
import shutil
build=E/'09_release';spec=json.loads((build/'PUBLIC_SELECTION.json').read_text());stage=E/'PUBLIC_STAGING';stage.mkdir(mode=0o755)
for rel,row in sorted(spec['files'].items()):
 s=build/'source'/rel;assert not s.is_symlink() and sha(s)==row['sha256'];q=stage/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,q);q.chmod(0o644)
assert set(str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file())==set(spec['files'])
cmds=[('public-git-init',['git','init','-b','main']),('public-git-stage',['git','add','--',*sorted(spec['files'])]),('public-git-commit',['git','-c','user.name=Aevora Release','-c','user.email=release@aevora.invalid','-c','commit.gpgsign=false','commit','-m','release: Aevora Gen2 public release candidate; explicit product-only export']),('public-rc-tag',['git','tag','aevora-gen2-rc1'])]
for label,args in cmds:
 if record(label,args,cwd=stage):raise RuntimeError(label)
clone=E/'CLEAN_PUBLIC_CLONE';assert record('public-independent-local-clone',['git','-c','core.hooksPath=/dev/null','clone','--no-hardlinks',stage,clone])==0
assert not (clone/'.git/objects/info/alternates').exists()
identity={n:subprocess.check_output(['git','rev-parse',v],cwd=stage,text=True).strip() for n,v in [('commit','HEAD'),('tree','HEAD^{tree}')]}
identity.update(source_commit=json.loads((E/'SOURCE_FREEZE.json').read_text())['commit'],files=len(spec['files']),stage=str(stage),clone=str(clone),tag='aevora-gen2-rc1',remote_push=False)
write(E/'PUBLIC_GIT_RECEIPT.json',identity);print(json.dumps(identity))
secret='/home/PRIVATE_MAINTAINER/.config/aevora/final-6312c046/public-clean'
env=dict(os.environ,AEVORA_IMAGE='aevora-gen2:6312c046-final')
raise SystemExit(record('public-final-clean-install',['python3','scripts/aevora_public_demo.py','start','--project','aevora-rc-6312c046','--secret-dir',secret,'--db-port','19072','--console-port','19074'],cwd=clone,env=env))
