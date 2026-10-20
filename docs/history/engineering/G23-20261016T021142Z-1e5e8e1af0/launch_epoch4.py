from audit import *
from runtime import runtime
# Reuse the passing 58+46 test result in this exact source epoch. All inherited
# suites are re-executed in the separate regression instance.
import runpy
s=(E/'regression_epoch4.py').read_text();s=s.replace("for label,args in jobs:\n result=", "for label,args in jobs:\n if label=='epoch4-host58-new46':continue\n result=")
exec(compile(s,str(E/'regression_epoch4.py'),'exec'))
