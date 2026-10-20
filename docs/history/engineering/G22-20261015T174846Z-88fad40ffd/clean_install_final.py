from pathlib import Path
import subprocess,json,sys
E=Path(__file__).parent
args=[str(E/'05_release/clean-venv-final2/bin/python'),'-I','-m','pip','install','--no-index','--no-deps','--force-reinstall',str(E/'05_release/public-final-build/dist/aevora_core-0.1.0-py3-none-any.whl'),str(E/'05_release/public-final-build/dist/aevora_console-0.1.0-py3-none-any.whl')]
r=subprocess.run(args,cwd=E);print(json.dumps(dict(argv=args,exit=r.returncode)));raise SystemExit(r.returncode)
