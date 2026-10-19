"""Current public wheel in a clean standalone venv; no Benchmark package install."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import uuid
import zipfile
from scripts.aevora_h3_audit import archive,write,digest,now,ROOT


def main():
    A=archive();parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();out=args.output.absolute() if args.output else A/'g2/standalone-install'
    if A not in out.parents:raise ValueError('Installation evidence belongs to this H3 archive')
    out.mkdir(parents=True,mode=0o700)
    source=out/'source';source.mkdir();shutil.copytree(ROOT/'aevora_core',source/'aevora_core',
        ignore=shutil.ignore_patterns('build','dist','*.egg-info','__pycache__','.pytest_cache','.venv'))
    commands=[]
    def run(args,cwd,env=None):
        start=now();r=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,timeout=300)
        d=out/('command-'+str(len(commands)+1));d.mkdir();(d/'stdout.log').write_bytes(r.stdout);(d/'stderr.log').write_bytes(r.stderr)
        row={'argv':list(map(str,args)),'cwd':str(cwd),'exit_code':r.returncode,'started_at':start,'ended_at':now(),
             'stdout_sha256':digest(d/'stdout.log'),'stderr_sha256':digest(d/'stderr.log')}
        write(d/'command.json',row);commands.append(row)
        if r.returncode:raise ValueError('Clean public installation command failed; receipt retained')
        return r.stdout
    distribution=out/'dist';distribution.mkdir()
    run([sys.executable,'-m','pip','wheel','--no-deps','--wheel-dir',distribution,str(source/'aevora_core')],source)
    wheels=list(distribution.glob('*.whl'));assert len(wheels)==1
    with zipfile.ZipFile(wheels[0]) as z:
        members=z.namelist();bad=[n for n in members if any(x in n for x in ['evaluator/','reference_patches/','private_manifests/','private_labels/','hidden_tests/','benchmark/','integrations/'])]
        if bad:raise ValueError('Private distribution members detected')
    write(out/'WHEEL_MEMBERS.json',{'sha256':digest(wheels[0]),'members':members,'private_matches':bad})
    venv=out/'venv';run([sys.executable,'-m','venv',venv],source)
    python=venv/'bin/python';run([python,'-m','pip','install',wheels[0]],source)
    run([python,'-m','pip','check'],source)
    clean=out/'clean-project';clean.mkdir();(clean/'context.json').write_text('{"concurrency_scope":"single_process_threads","shared_state_kind":"sqlite_file"}\n')
    environment={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','PYTHONHOME']}
    environment['AEVORA_FALKORDB_GRAPH']='aevora_h3_standalone_'+uuid.uuid4().hex
    run([python,'-I','-m','aevora','init'],clean,environment)
    output=run([python,'-I','-m','aevora','query','--run-id','clean-standalone-query','--context',clean/'context.json'],clean,environment)
    query=json.loads(output);assert query['status']=='AVAILABLE' and query['candidates']==[]
    run([python,'-I','-c',"import importlib.util; assert importlib.util.find_spec('benchmark') is None; assert importlib.util.find_spec('integrations') is None; import aevora.cli; print('CORE_ONLY_IMPORT_PASS')"],clean,environment)
    run([python,'-m','pip','uninstall','-y','aevora-core'],clean,environment)
    run([python,'-I','-c',"import importlib.util; assert importlib.util.find_spec('aevora') is None; print('UNINSTALL_CONFIRMED')"],clean,environment)
    write(out/'RESULT.json',{'status':'PASS','commands':commands,'wheel_sha256':digest(wheels[0]),
        'minimal_query':query,'core_without_benchmark':'PASS','uninstall':'PASS','native_model_calls':0,
        'graph':environment['AEVORA_FALKORDB_GRAPH'],'interpretation':'Actual clean package/SDK query; not a native project challenge'})
    print(json.dumps({'status':'PASS','commands':len(commands),'wheel_sha256':digest(wheels[0]),'model_calls':0}));return 0


if __name__=='__main__':raise SystemExit(main())
