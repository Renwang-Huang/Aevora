"""Build local native snapshot archives with pinned mature release tools.

No publication, signing, upload, package-manager install, source mutation or
implicit output cleanup. A clean committed source and fresh external output
are required. Cross-builds are never labeled native platform validation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tools.paths import fresh_external_output
from tools.native_assets import synchronize

ROOT=Path(__file__).resolve().parents[1]
TARGETS=['linux/amd64','linux/arm64','darwin/amd64','darwin/arm64','windows/amd64']


def run(command,env,cwd=ROOT/'go-runtime',log=None):
    if log:
        with log.open('xb') as f:subprocess.run(command,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        return ''
    return subprocess.check_output(command,cwd=cwd,env=env,text=True)


def build(output,*,go,goreleaser,licenses,version,stable=False):
    pattern=r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'
    if not re.fullmatch(pattern if stable else pattern+r'-dev(?:\.[A-Za-z0-9.-]+)?',version):
        raise ValueError('Stable artifacts require --stable with an exact release version; snapshots require a development version')
    env={**os.environ,'CGO_ENABLED':'0','PYTHONDONTWRITEBYTECODE':'1','PATH':str(Path(go).parent)+os.pathsep+os.environ.get('PATH','')}
    if run(['git','status','--porcelain','-uall'],env,ROOT).strip():raise ValueError('Commit functional changes before building a reviewable snapshot')
    revision=run(['git','rev-parse','HEAD'],env,ROOT).strip()
    synchronize(check=True)
    tool_version=run([str(goreleaser),'--version'],env)
    if not re.search(r'\b2\.19\.0\b',tool_version):raise ValueError('GoReleaser v2.19.0 required')
    license_build=run([str(go),'version','-m',str(licenses)],env)
    if not any(line.split()[:3]==['mod','github.com/google/go-licenses/v2','v2.0.1'] for line in license_build.splitlines()):raise ValueError('google/go-licenses v2.0.1 required')
    output=fresh_external_output(output,ROOT);output.mkdir(parents=True)
    notices={};modules={};by_target={};license_root=output/'licenses';license_root.mkdir()
    for target in TARGETS:
        target_os,target_arch=target.split('/');target_env={**env,'GOOS':target_os,'GOARCH':target_arch};label=target.replace('/','-')
        saved=license_root/label
        run([str(licenses),'save','./cmd/aevora','--ignore=github.com/Renwang-Huang/Aevora','--save_path',str(saved)],target_env,log=output/(label+'-licenses.log'))
        dependencies=run([str(go),'list','-deps','-f','{{with .Module}}{{.Path}} {{.Version}} {{.Sum}}{{end}}','./cmd/aevora'],target_env)
        required={};
        for line in dependencies.splitlines():
            values=line.split()
            if not values:continue
            if values[0]=='github.com/Renwang-Huang/Aevora/go-runtime':continue
            if len(values)!=3 or not values[2].startswith('h1:'):raise ValueError('Pinned version and sum required for every linked external module')
            required[values[0]]={'version':values[1],'sum':values[2]}
            if values[0] in modules and modules[values[0]]!=required[values[0]]:raise ValueError('Target module versions differ')
            modules[values[0]]=required[values[0]]
        by_target[target]=required
        for p in sorted(saved.rglob('*')):
            if p.is_file():
                if p.is_symlink() or p.stat().st_size>8*1024*1024:raise ValueError('Unexpected license artifact')
                raw=p.read_bytes();key=str(p.relative_to(saved))
                if key in notices and notices[key]!=raw:raise ValueError('Conflicting target license bytes')
                notices[key]=raw
    # Keep upstream supplementary notices, including transpiled C dependencies.
    # go-licenses supplies classification; these copies retain complete texts.
    for name in sorted(modules):
        module=json.loads(run([str(go),'list','-m','-json',name],env))
        if module.get('Replace'):raise ValueError('Release replacements require explicit separate review')
        directory=Path(module['Dir'])
        for p in sorted(directory.iterdir()):
            if p.is_file() and not p.is_symlink() and p.suffix!='.go' and p.name.lower().startswith(('license','copying','notice','copyright')):
                if p.stat().st_size>8*1024*1024:raise ValueError('Oversized upstream notice')
                notices[name+'@'+modules[name]['version']+'/'+p.name]=p.read_bytes()
    goroot=Path(run([str(go),'env','GOROOT'],env).strip())
    notices['Go/LICENSE']=(goroot/'LICENSE').read_bytes()
    notices['Cytoscape.js/LICENSE']=(ROOT/'console/third_party/CYTOSCAPE_LICENSE').read_bytes()
    aggregate=license_root/'THIRD-PARTY-LICENSES.txt'
    with aggregate.open('xb') as f:
        f.write(b'Complete upstream license and notice texts for this Aevora native build.\n')
        for name,raw in sorted(notices.items()):f.write(('\n===== '+name+' =====\n').encode());f.write(raw);f.write(b'\n')
    # GoReleaser's dist field is a literal path, not a template-capable field.
    # Materialize only that field into an external configuration; source stays clean.
    template=(ROOT/'go-runtime/.goreleaser.yaml').read_text()
    if template.splitlines().count('dist: dist')!=1:raise ValueError('Expected one literal distribution directory')
    config=output/'goreleaser.yaml'
    config.write_text(template.replace('dist: dist\n','dist: '+json.dumps(str(output/'dist'))+'\n',1))
    # Snapshot mode tolerates absent remotes and can report FullCommit=none.
    # Bind the binary to our independently verified local source revision.
    env.update(AEVORA_NATIVE_LICENSES=str(license_root),AEVORA_NATIVE_VERSION=version,AEVORA_NATIVE_REVISION=revision)
    run([str(goreleaser),'check','--config',str(config)],env,log=output/'goreleaser-check.log')
    run([str(goreleaser),'release','--snapshot','--skip=publish','--config',str(config)],env,log=output/'goreleaser-build.log')
    artifacts={str(p.relative_to(output/'dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((output/'dist').iterdir()) if p.is_file() and p.suffix in {'.gz','.zip','.txt','.json'}}
    report={'schema_version':'aevora.native-distribution/1','status':'BUILT_NOT_RUNTIME_VALIDATED','source_revision':revision,'version':version,'artifact_channel':'STABLE_CANDIDATE' if stable else 'DEVELOPMENT_SNAPSHOT','goreleaser':'v2.19.0','go_licenses':'v2.0.1','targets':by_target,'artifacts_sha256':artifacts,'license_bundle_sha256':hashlib.sha256(aggregate.read_bytes()).hexdigest(),'license_files':len(notices),'publication':'DISABLED','native_platform_validation':'NOT_PERFORMED_BY_CROSS_BUILD'}
    with (output/'BUILD.json').open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--go',type=Path,required=True);parser.add_argument('--goreleaser',type=Path,required=True);parser.add_argument('--go-licenses',type=Path,required=True);parser.add_argument('--version',default='0.4.0-dev');parser.add_argument('--stable',action='store_true',help='Build exact-version stable candidate artifacts; never publishes or establishes platform acceptance');args=parser.parse_args()
    result=build(args.output,go=args.go,goreleaser=args.goreleaser,licenses=args.go_licenses,version=args.version,stable=args.stable)
    print(json.dumps({'status':result['status'],'targets':list(result['targets']),'output':str(args.output),'publication':'DISABLED'}))
