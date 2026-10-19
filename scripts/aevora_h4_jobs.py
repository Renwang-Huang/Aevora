"""Detached evidence command receipts survive interactive turn boundaries.

This is a maintainer validation process owner, not an Agent planner/orchestrator.
It runs one existing command unchanged and records its real terminal exit.
"""
import argparse,json,os,signal,subprocess
from pathlib import Path
from scripts.aevora_h4_audit import ROOT,archive,record,write,digest,now,launch

def start(label,argv):
    A=archive();job=A/'jobs'/label;job.mkdir(parents=True,mode=0o700)
    stdout=(job/'owner-stdout.log').open('xb');stderr=(job/'owner-stderr.log').open('xb')
    command=['python3','-m','scripts.aevora_h4_audit','record',label,'--',*argv]
    proc=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
    stdout.close();stderr.close();stat=Path('/proc')/str(proc.pid)/'stat';stamp=stat.read_text().rsplit(')',1)[1].split()[19]
    write(job/'START.json',{'pid':proc.pid,'proc_start_ticks':stamp,'argv':command,'at':now(),'scope':'One existing evidence command, owner outside interactive tool session'})
    print(json.dumps({'label':label,'pid':proc.pid,'status':'STARTED'}));return proc.pid

def stop(label):
    job=archive()/'jobs'/label;v=json.loads((job/'START.json').read_text());p=Path('/proc')/str(v['pid'])/'stat'
    if not p.exists():raise ValueError('Owned PID absent; do not signal a replacement')
    if p.read_text().rsplit(')',1)[1].split()[19]!=v['proc_start_ticks']:raise ValueError('PID reused; refused')
    if 'aevora_observatory.server' not in v['argv']:raise ValueError('Only an owned Viewer service may be stopped here; use RuntimeControl for Agent cancellation')
    children=(Path('/proc')/str(v['pid'])/'task'/str(v['pid'])/'children').read_text().split()
    if len(children)!=1:raise ValueError('Expected exactly one actual owned command child')
    child=int(children[0]);os.kill(child,signal.SIGTERM)
    write(job/'STOP_REQUEST.json',{'at':now(),'pid':v['pid'],'actual_command_pid':child,'owner_signal':'SIGTERM','receipt_owner_kept_alive':True})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['start','stop']);p.add_argument('label');p.add_argument('argv',nargs=argparse.REMAINDER);a=p.parse_args()
    if not a.label.replace('-','').isalnum():raise ValueError('Simple unique label required')
    if a.operation=='stop':stop(a.label)
    else:start(a.label,a.argv[1:] if a.argv[:1]==['--'] else a.argv)
