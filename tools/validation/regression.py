"""Current full JUnit/raw Cypher collection using the unchanged H4 test runner.

Explicit owned endpoint guard replaces phase-default path assumptions. Collection
is not business code, an Oracle or an Agent orchestrator.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse,os,sys,time,json
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import aevora_h4_tests as runner
@contextmanager
def owned_maintenance(output,repo,port):
    if os.environ.get('AEVORA_FALKORDB_HOST','127.0.0.1')!='127.0.0.1' or int(os.environ.get('AEVORA_FALKORDB_PORT','0'))!=port:raise ValueError('Explicit owned loopback endpoint required')
    conn=repo._client.connection;original=conn.config_get('save');receipt={'owned_port':port,'original_save':original}
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
            runner.write(output/'MAINTENANCE.json',receipt)
            assert receipt['restore_result'] is True and receipt['after']==original

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--owned-port',required=True,type=int);p.add_argument('pytest_args',nargs=argparse.REMAINDER);a=p.parse_args(argv)
    from tools.paths import fresh_external_output
    output=fresh_external_output(a.output,ROOT)
    if not 1024<=a.owned_port<=65535:raise ValueError('Explicit owned nonprivileged endpoint required')
    args=a.pytest_args[1:] if a.pytest_args[:1]==['--'] else a.pytest_args
    runner.maintenance=lambda out,repo:owned_maintenance(out,repo,a.owned_port)
    def epoch():
        folders=['app','benchmark','evaluator','integrations','aevora_core/src','console/src','aevora_maintainer','tools','tests','aevora_core/tests']
        return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for folder in folders for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}
    before=epoch();code=runner.main(output,args or ['-q','tests','aevora_core/tests']);after=epoch()
    runner.write(output/'RUNTIME_SOURCE_EPOCH.json',{'before':before,'after':after,'unchanged':before==after})
    if before!=after:raise RuntimeError('Execution sources changed during validation')
    return code
if __name__=='__main__':raise SystemExit(main())
