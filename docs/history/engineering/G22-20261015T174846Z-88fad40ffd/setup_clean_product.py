from pathlib import Path
import sys,shutil,json
E=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/G22-20261015T174846Z-88fad40ffd');sys.path.insert(0,str(E));from audit import *
old=E.parent/'G21-20261015T152946Z-354ffd0684'
(E/'05_release').mkdir(exist_ok=True);clean=E/'05_release/clean-venv-final2'
shutil.copytree(E/'venv',clean,symlinks=True,ignore=shutil.ignore_patterns('__editable__*','orderflow_incident_lab-*.dist-info'))
for p in (clean/'lib/python3.12/site-packages').glob('*'):
 if p.name.startswith('orderflow'):
  # Only fresh copied maintainer metadata, never a source or old environment.
  if p.is_dir():shutil.rmtree(p)
  else:p.unlink()
script=(old/'public_smoke_final.py').read_text().replace('aevora_g21_public_install_','aevora_g22_public_install_').replace('v5c1-public-','g22-public-').replace('/clean-venv-final/','/clean-venv-final2/')
script=script.replace("check('public_wheel_imports'", "import importlib.util\ncheck('host_facade_absent',importlib.util.find_spec('aevora_maintainer') is None,'private Host facade not installed or mounted')\ncheck('public_wheel_imports'")
(E/'public_smoke_final.py').write_text(script)
(E/'run_public_smoke_final.py').write_text((old/'run_public_smoke_final.py').read_text().replace('clean-venv-final','clean-venv-final2').replace('g21-clean-public-real-mcp-console-final','g22-clean-public-real-mcp-console-final'))
(E/'clean_install_final.py').write_text('''from pathlib import Path
import subprocess,json,sys
E=Path(__file__).parent
args=[str(E/'05_release/clean-venv-final2/bin/python'),'-I','-m','pip','install','--no-index','--no-deps','--force-reinstall',str(E/'05_release/public-final-build/dist/aevora_core-0.1.0-py3-none-any.whl'),str(E/'05_release/public-final-build/dist/aevora_console-0.1.0-py3-none-any.whl')]
r=subprocess.run(args,cwd=E);print(json.dumps(dict(argv=args,exit=r.returncode)));raise SystemExit(r.returncode)
''')
print('fresh clean product setup complete')
