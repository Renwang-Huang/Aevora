from audit import *
from runtime import runtime
import shutil
old=E.parent/'G22-20261015T174846Z-88fad40ffd'
assert record('public-build',runtime(E/'build_reproducible.py','public-final-build'))==0
clean=E/'05_release/clean-venv-final2'
shutil.copytree(E/'venv',clean,symlinks=True,ignore=shutil.ignore_patterns('__editable__*','orderflow*'))
for name in ['public_smoke_final.py','run_public_smoke_final.py','clean_install_final.py']:
 s=(old/name).read_text().replace('aevora_g22_public_install_','aevora_g23_public_install_').replace('g22-public-','g23-public-').replace('g22-clean-public-real-mcp-console-final','g23-clean-public-real-mcp-console-final')
 (E/name).write_text(s)
assert record('clean-wheel-install',runtime(E/'clean_install_final.py'))==0
assert record('clean-product-owner',['python3','-B',str(E/'run_public_smoke_final.py')],cwd=E)==0
