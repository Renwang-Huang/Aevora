from pathlib import Path
import os,subprocess,sys
E=Path(__file__).parent
import hashlib,json,shutil
files={str(f.relative_to(E/'worktree')):hashlib.sha256(f.read_bytes()).hexdigest() for base in ['aevora_core/src','aevora_maintainer','aevora_core/tests/g22','tools/validation'] for f in (E/'worktree'/base).rglob('*.py') if '__pycache__' not in f.parts}
(E/('SOURCE_'+sys.argv[1]+'.json')).write_text(json.dumps(files,sort_keys=True))
snapshot=E/'source_history'/sys.argv[1];snapshot.mkdir()
for rel in files:
 target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(E/'worktree'/rel,target)
os.environ['AEVORA_G22_ARTIFACT_ROOT']=str(E/'02_publication'/sys.argv[1])
Path(os.environ['AEVORA_G22_ARTIFACT_ROOT']).mkdir()
os.environ['AEVORA_G22_CASES']=str(E/'01_admission/verified-runs/CASES.json')
raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q','aevora_core/tests/g22','-p','no:cacheprovider','--junitxml='+str(E/('host-'+sys.argv[1]+'.xml')),*sys.argv[2:]]))
