#!/usr/bin/env python3
"""Run one non-secret argv and archive exact command, exit and separate logs."""
import datetime,json,pathlib,subprocess,sys,time
archive=pathlib.Path(sys.argv[1]); archive.mkdir(parents=True,exist_ok=False)
command=sys.argv[2:]
started=datetime.datetime.now(datetime.timezone.utc).isoformat(); t=time.monotonic()
with (archive/'stdout.log').open('wb') as out,(archive/'stderr.log').open('wb') as err:
 result=subprocess.run(command,stdout=out,stderr=err)
record={'argv':command,'cwd':str(pathlib.Path.cwd()),'started_at':started,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-t,'exit_code':result.returncode}
(archive/'command.json').write_text(json.dumps(record,indent=2)+'\n'); print(json.dumps(record)); raise SystemExit(result.returncode)
