#!/usr/bin/env python3
"""Start/stop an explicitly named local public Demo. Never deletes a volume."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['start','stop','status']);p.add_argument('--project',default='aevora-gen2-demo');p.add_argument('--secret-dir',type=Path,required=True);p.add_argument('--db-port',type=int,default=19062);p.add_argument('--console-port',type=int,default=19064);a=p.parse_args()
    if not re.fullmatch(r'aevora-[a-z0-9][a-z0-9-]{0,48}',a.project):raise SystemExit('Use an explicit aevora- project name')
    if not all(1024<=n<=65535 for n in [a.db_port,a.console_port]) or a.db_port==a.console_port:raise SystemExit('Invalid distinct local ports')
    root=Path(__file__).resolve().parents[1];secret=a.secret_dir.absolute()
    if a.command=='start':
        subprocess.run([sys.executable,str(root/'scripts/aevora_bootstrap.py'),str(secret)],check=True)
    env=dict(os.environ,AEVORA_UID=str(os.getuid()),AEVORA_GID=str(os.getgid()),AEVORA_FALKORDB_PASSWORD_FILE=str(secret/'falkordb.password'),AEVORA_REDIS_CONFIG_FILE=str(secret/'falkordb.conf'),AEVORA_DB_PORT=str(a.db_port),AEVORA_CONSOLE_PORT=str(a.console_port))
    base=['docker','compose','-p',a.project,'-f',str(root/'deploy/compose.yaml')]
    if a.command=='stop':
        # Save this explicitly owned instance before graceful stop. No crash-tail
        # durability or production recovery claim is made.
        save="from aevora.graph_repository import GraphRepository;r=GraphRepository.from_environment();assert r._client.connection.save() is True;r.close();print('Explicit owned RDB SAVE complete')"
        subprocess.run(base+['exec','-T','console','python','-c',save],env=env,check=True)
    command={'start':['up','-d','--build','--wait'],'stop':['stop'],'status':['ps']}[a.command]
    subprocess.run(base+command,env=env,check=True)
    if a.command=='start':print(f'Aevora LIVE synthetic demo: http://127.0.0.1:{a.console_port}/journey.html')
if __name__=='__main__':main()
