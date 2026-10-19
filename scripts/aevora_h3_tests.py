"""Current H3 real-graph pytest with raw Cypher, source epoch and bounded SAVE maintenance."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import sys
import threading
import time
from scripts.aevora_h2_audit import digest, write, now, ROOT


@contextmanager
def maintenance(output, repo):
    if os.environ.get('AEVORA_FALKORDB_PORT') != '17689':
        raise ValueError('Only independently owned H3 endpoint17689 allowed')
    connection=repo._client.connection; original=connection.config_get('save')
    receipt={'original_save':original,'port':17689,'classification':'Temporary isolated test window, not RPO upgrade'}
    def drain():
        end=time.monotonic()+5
        while True:
            state=connection.info('persistence')
            if not any(state.get(k,0) for k in ['rdb_bgsave_in_progress','aof_rewrite_in_progress','module_fork_in_progress']):return state
            if time.monotonic()>end:raise RuntimeError('Fork drain bounded deadline exceeded')
            time.sleep(.02)
    try:
        receipt['pause_result']=connection.config_set('save','');assert receipt['pause_result'] is True
        receipt['before']=drain();yield
    finally:
        try:
            receipt['before_save']=drain();receipt['save_result']=connection.save()
        finally:
            receipt['restore_result']=connection.config_set('save',original['save']);receipt['after']=connection.config_get('save')
            write(output/'MAINTENANCE.json',receipt)
            assert receipt['restore_result'] is True and receipt['after']==original


def main(output,args):
    from aevora.graph_repository import GraphRepository
    import pytest
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    epoch={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'aevora_core/src/aevora').glob('*.py'))}
    write(output/'SOURCE_EPOCH.json',epoch)
    original=GraphRepository.query; lock=threading.Lock();count=0;total=0
    log=(output/'RAW_CYPHER.jsonl').open('x')
    def query(repo,statement,params=None,*,read_only=True):
        nonlocal count,total
        row={'graph':repo.graph_name,'statement':statement,'params':params or {},'read_only':read_only,'started_at':now()}
        try:
            value=original(repo,statement,params,read_only=read_only);row.update(status='RETURNED',rows=value);return value
        except Exception as e:
            row.update(status='ERROR',error_type=type(e).__name__);raise
        finally:
            row['ended_at']=now()
            raw=json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n'
            with lock:
                total+=len(raw.encode());count+=1
                if total>256*1024*1024:raise RuntimeError('Raw evidence finite budget exceeded')
                log.write(raw);log.flush()
    repo=GraphRepository.from_environment()
    GraphRepository.query=query
    try:
        with maintenance(output,repo):code=pytest.main([*args,'--junitxml='+str(output/'JUNIT.xml')])
    finally:
        GraphRepository.query=original;repo.close();log.close()
        write(output/'RAW_RECEIPT.json',{'queries':count,'bytes':total,'sha256':digest(output/'RAW_CYPHER.jsonl'),'pytest_exit':locals().get('code','UNAVAILABLE')})
    assert epoch=={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'aevora_core/src/aevora').glob('*.py'))},'Source changed during tests'
    return code


if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1]).absolute(),sys.argv[2:] or ['-q','tests','aevora_core/tests']))
