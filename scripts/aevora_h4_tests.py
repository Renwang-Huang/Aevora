"""Actual full pytest with raw SDK queries and owned H4 SAVE/fork maintenance."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import threading
import time
from scripts.aevora_h4_audit import ROOT,archive,write,digest,now


@contextmanager
def maintenance(output,repo):
    if os.environ.get('AEVORA_FALKORDB_PORT')!='17692':raise ValueError('Only owned H4 endpoint17692 permitted')
    conn=repo._client.connection;original=conn.config_get('save');receipt={'original_save':original,'port':17692}
    def drain():
        end=time.monotonic()+5
        while True:
            info=conn.info('persistence')
            if not any(info.get(k,0) for k in ['rdb_bgsave_in_progress','aof_rewrite_in_progress','module_fork_in_progress']):return info
            if time.monotonic()>end:raise RuntimeError('Owned maintenance fork drain timed out')
            time.sleep(.02)
    try:
        receipt['pause_result']=conn.config_set('save','');assert receipt['pause_result'] is True
        receipt['before']=drain();yield
    finally:
        try:receipt['before_save']=drain();receipt['save_result']=conn.save()
        finally:
            receipt['restore_result']=conn.config_set('save',original['save']);receipt['after']=conn.config_get('save')
            write(output/'MAINTENANCE.json',receipt)
            assert receipt['restore_result'] is True and receipt['after']==original


def main(output,args):
    from aevora.graph_repository import GraphRepository
    import pytest
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    epoch={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'aevora_core/src/aevora').glob('*.py'))}
    write(output/'SOURCE_EPOCH.json',epoch);original=GraphRepository.query;lock=threading.Lock();count=0;total=0
    log=(output/'RAW_CYPHER.jsonl').open('x')
    def query(repo,statement,params=None,*,read_only=True):
        nonlocal count,total
        row={'graph':repo.graph_name,'statement':statement,'params':params or {},'read_only':read_only,'started_at':now()}
        try:v=original(repo,statement,params,read_only=read_only);row.update(status='RETURNED',rows=v);return v
        except Exception as e:row.update(status='ERROR',error_type=type(e).__name__);raise
        finally:
            row['ended_at']=now();raw=json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n'
            with lock:
                total+=len(raw.encode());count+=1
                if total>256*1024*1024:raise RuntimeError('Raw evidence finite size exceeded')
                log.write(raw);log.flush()
    repo=GraphRepository.from_environment();GraphRepository.query=query
    try:
        with maintenance(output,repo):code=pytest.main([*args,'--junitxml='+str(output/'JUNIT.xml')])
    finally:
        GraphRepository.query=original;repo.close();log.close()
        write(output/'RAW_RECEIPT.json',{'queries':count,'bytes':total,'sha256':digest(output/'RAW_CYPHER.jsonl'),'pytest_exit':locals().get('code','UNAVAILABLE')})
    assert epoch=={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'aevora_core/src/aevora').glob('*.py'))},'Core changed during tests'
    return code


if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1]).absolute(),sys.argv[2:] or ['-q','tests','aevora_core/tests']))
