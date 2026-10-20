from pathlib import Path
import os,sys
E=Path(__file__).parent
os.environ['AEVORA_G22_CASES']=str(E/'01_admission/final-cases/CASES.json')
from tools.validation.g22_tests import main
raise SystemExit(main())
