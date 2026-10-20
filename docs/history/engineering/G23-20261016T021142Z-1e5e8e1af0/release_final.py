from audit import *
from runtime import runtime
import shutil
old=E.parent/'G22-20261015T174846Z-88fad40ffd'
s=(E/'build_reproducible.py').read_text().replace("E/'05_release'","E/'09_release_final'");(E/'build_reproducible_final.py').write_text(s)
assert record('epoch3-public-build',runtime(E/'build_reproducible_final.py','public-final-build',profile='REGRESSION'))==0
clean=E/'09_release_final/clean-venv-final2';shutil.copytree(E/'venv',clean,symlinks=True,ignore=shutil.ignore_patterns('__editable__*','orderflow*'))
for name in ['public_smoke_final.py','run_public_smoke_final.py','clean_install_final.py']:
 s=(old/name).read_text().replace('aevora_g22_public_install_','aevora_g23_final_public_').replace('g22-public-','g23-public-').replace('g22-clean-public-real-mcp-console-final','g23-final-clean-public').replace('05_release/','09_release_final/')
 if name=='run_public_smoke_final.py':s=s.replace("E/'RUNTIME_CONFIG.json'","E/'RUNTIME_REGRESSION_CONFIG.json'")
 newname=name.replace('_final.py','_epoch3.py');(E/newname).write_text(s)
 if name=='run_public_smoke_final.py':
  q=E/newname;q.write_text(q.read_text().replace("E/'public_smoke_final.py'","E/'public_smoke_epoch3.py'"))
assert record('epoch3-clean-install',runtime(E/'clean_install_epoch3.py',profile='REGRESSION'))==0
assert record('epoch3-clean-product-owner',['python3','-B',str(E/'run_public_smoke_epoch3.py')],cwd=E)==0
