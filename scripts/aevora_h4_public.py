"""Explicit public product source selection, deterministic ZIP, real wheel/sdist build."""
import argparse,json,os,shutil,stat,subprocess,tarfile,zipfile
from pathlib import Path
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now,record,launch

SKIP={'__pycache__','.pytest_cache','.git','node_modules','.venv','build','dist'}
DOCS=['QUICKSTART.md','CODEX_MCP_SETUP.md','TROUBLESHOOTING.md','H4_HERO_SCENARIO.md','H4_OBSERVATORY_API.md','UI_COMPONENT_EVIDENCE_MATRIX.csv','GRAPH_MODEL_AND_CYPHER.md','DEMO_WALKTHROUGH.md','DEMO_RECORDING_GUIDE.md','PRODUCT_LIMITATIONS.md','AI_DISCLOSURE.md','COMPETITION_REQUIREMENTS_CHECKLIST.md','THIRD_PARTY_NOTICES.md']

def chosen():
    paths=set()
    bases=['aevora_core/src','aevora_core/docs','aevora_core/examples/receipt_store','console/src','console/web','console/third_party','h4']
    for base in bases:
        for p in (ROOT/base).rglob('*'):
            if p.is_file() and not p.is_symlink() and not set(p.parts)&SKIP and not any(x.endswith('.egg-info') for x in p.parts):paths.add(p)
    for folder,names in [('aevora_core',['README.md','pyproject.toml','MANIFEST.in','LICENSE']),('console',['README.md','pyproject.toml','MANIFEST.in','LICENSE','package.json','package-lock.json','build.mjs','sync_evidence_tools.py','.nvmrc'])]:
        paths.update(ROOT/folder/n for n in names)
    paths.update(ROOT/'docs'/n for n in DOCS);paths.add(ROOT/'scripts/aevora_bootstrap.py')
    return sorted(paths)


def make(label):
    A=archive();out=A/'g5'/label;out.mkdir(mode=0o700);source=out/'source';source.mkdir()
    rows={}
    for p in chosen():
        if not p.is_file() or p.is_symlink():raise ValueError('Public input not ordinary')
        rel=str(p.relative_to(ROOT));dest=source/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);dest.chmod(p.stat().st_mode&0o777);rows[rel]={'sha256':digest(dest),'source_sha256':digest(p),'visibility':'PUBLIC'}
    for src,dest in [('docs/PUBLIC_README.md','README.md'),('aevora_core/LICENSE','LICENSE'),('docs/THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.md')]:shutil.copyfile(ROOT/src,source/dest)
    (source/'.gitignore').write_text('.venv/\nnode_modules/\n__pycache__/\nbuild/\ndist/\n*.egg-info/\n*.key\n*.password\ngrant.json\n')
    (source/'.dockerignore').write_text('.git\n**/__pycache__\n**/node_modules\n**/build\n**/dist\n**/*.egg-info\n**/*.key\n**/*.password\n')
    write(out/'PUBLIC_SELECTION.json',{'files':rows,'at':now(),'excluded':'All Benchmark maintainer/hidden/reference/private labels, root AGENTS, archives, keys, scoped grants; selection is an explicit allowlist','root_readme_source_sha256':digest(ROOT/'docs/PUBLIC_README.md')})
    env={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null'}
    git=[]
    for args in [['init','-b','aevora-public-local'],['add','--','.'],['-c','user.name=Aevora Local Release','-c','user.email=aevora@invalid','commit','-m','Aevora H4 public product source']]:
        cmd=['git','-c','core.hooksPath=/dev/null',*args];r=subprocess.run(cmd,cwd=source,env=env,capture_output=True,text=True);git.append({'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip();write(out/'PUBLIC_GIT.json',{'commit':commit,'tree':tree,'commands':git,'remote_published':False,'at':now()})
    dist=out/'dist';dist.mkdir()
    for folder in ['aevora_core','console']:
        code="import os;from setuptools.build_meta import build_wheel,build_sdist;os.chdir("+repr(str(source/folder))+");print(build_wheel("+repr(str(dist))+"));print(build_sdist("+repr(str(dist))+"))"
        rc=record(A,label+'-build-'+folder,launch('-c',code));assert rc==0
    files={str(p.relative_to(source)):digest(p) for p in source.rglob('*') if p.is_file() and not p.is_symlink() and not set(p.relative_to(source).parts)&SKIP and not any(x.endswith('.egg-info') for x in p.parts)}
    zipfile_path=out/'aevora-h4-public-source.zip'
    def export(path):
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for rel in sorted(files):
                b=(source/rel).read_bytes();assert digest(source/rel)==files[rel];info=zipfile.ZipInfo('aevora/'+rel,date_time=(1980,1,1,0,0,0));info.external_attr=(stat.S_IFREG|0o644)<<16;z.writestr(info,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    export(zipfile_path);repeat=out/'aevora-h4-public-source-repeat.zip';export(repeat);assert digest(zipfile_path)==digest(repeat)
    write(out/'RESULT.json',{'status':'PASS','source_commit':commit,'source_tree':tree,'source_files':files,'source_zip_sha256':digest(zipfile_path),'source_zip_bytes':zipfile_path.stat().st_size,'artifacts':{p.name:digest(p) for p in dist.iterdir()},'deterministic_source_zip_equal':True,'at':now(),'distribution':'LOCAL_ONLY; not public hosting or official submission'})
    print(json.dumps({'status':'PASS','source_files':len(files),'artifacts':len(list(dist.iterdir())),'source_zip_bytes':zipfile_path.stat().st_size}));return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);args=p.parse_args();raise SystemExit(make(args.label))
