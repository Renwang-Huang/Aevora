from pathlib import Path
import os,subprocess,sys,json,hashlib
from tools.public_release import build
E=Path(__file__).parent;P=E/'worktree'
epoch=subprocess.check_output(['git','show','-s','--format=%ct','HEAD'],cwd=P,text=True).strip();os.environ['SOURCE_DATE_EPOCH']=epoch
out=E/'05_release'/sys.argv[1]
result=build(out)
(out/'REPRODUCIBLE_PROFILE.json').write_text(json.dumps(dict(SOURCE_DATE_EPOCH=epoch,origin='actual source commit timestamp, only build ZIP member normalization',actual_execution_times='commands receipts',standard='https://reproducible-builds.org/docs/source-date-epoch/')))
