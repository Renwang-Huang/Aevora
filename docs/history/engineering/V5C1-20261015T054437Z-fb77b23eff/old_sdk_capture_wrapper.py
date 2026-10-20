"""Trusted finite measurement tee; original public broker bounds are unchanged."""
from pathlib import Path
import sys,subprocess,threading
E=Path(__file__).resolve().parent
p=subprocess.Popen([sys.executable,'-u',str(E/'old_sdk_entry.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,bufsize=0)
def forward_input():
 try:
  for raw in sys.stdin.buffer:
   if len(raw)>262144:raise RuntimeError('trusted input capture bound')
   p.stdin.write(raw);p.stdin.flush()
 except (BrokenPipeError,OSError):pass
threading.Thread(target=forward_input,daemon=True).start()
with (E/'01_root_cause/exact_old_broker_replay/exact_sdk_stdout.jsonl').open('xb',buffering=0) as capture:
 for _ in range(8):
  raw=p.stdout.readline(8*1024*1024+1)
  if not raw:break
  if len(raw)>8*1024*1024 or not raw.endswith(b'\n'):raise RuntimeError('trusted 8MiB measurement bound')
  capture.write(raw) # Entire exact rejected frame is persisted BEFORE its first broker byte.
  sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
