"""Current command map. Execute one mature command, with no scheduling runtime."""
import argparse,os,subprocess,sys
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMANDS=('check-sources','build-console','test-console','test-core','test-maintainer','test-graph-v2','host-case-generate','test-host-v2','public-build','benchmark-check','dv02-check','db-init','db-health','console-replay','console-live','mcp-config')
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=COMMANDS);p.add_argument('--output',type=Path);p.add_argument('--owned-port',type=int);p.add_argument('--port',type=int,default=17804);a,extra=p.parse_known_args(argv)
    py=sys.executable;pin=sha256((ROOT/'examples/observatory/hero_scenario_contract.json').read_bytes()).hexdigest();extra=extra[1:] if extra[:1]==['--'] else extra
    output=a.output.absolute() if a.output else None
    if a.command in {'test-maintainer','test-graph-v2','host-case-generate','test-host-v2','public-build','benchmark-check','dv02-check','test-core'} and (output is None or output.is_relative_to(ROOT)):p.error('Fresh external --output required')
    if output is not None and a.command in {'test-maintainer','test-graph-v2','host-case-generate','test-host-v2','public-build','benchmark-check','dv02-check','test-core'}:
        sys.path.insert(0,str(ROOT))
        from tools.paths import fresh_external_output
        output=fresh_external_output(output,ROOT)
    if a.command in {'test-maintainer','test-graph-v2','test-host-v2'} and a.owned_port is None:p.error('--owned-port is required; no historic endpoint defaults')
    args={
      'check-sources':[py,'tools/sync_public_evidence.py','--check'],
      'build-console':['npm','--prefix','console','run','build'],
      'test-console':['npm','--prefix','console','test'],
      'test-core':[py,'-m','pytest','-q','aevora_core/tests','--junitxml='+str(output/'JUNIT.xml') if output else ''],
      'test-graph-v2':[py,'tools/validation/g21_tests.py','--output',str(output),'--owned-port',str(a.owned_port)],
      'host-case-generate':[py,'tools/validation/g22_host_cases.py','--output',str(output)],
      'test-host-v2':[py,'tools/validation/g22_tests.py','--output',str(output),'--owned-port',str(a.owned_port),'--','-q','aevora_core/tests/g22','-p','no:cacheprovider'],
      'test-maintainer':[py,'tools/validation/regression.py','--output',str(output),'--owned-port',str(a.owned_port)],
      'public-build':[py,'tools/public_release.py','--output',str(output)],
      'benchmark-check':[py,'scripts/aevora_h2_cli_regression.py',str(output),'--cli-module','benchmark.h2_cli'],
      'dv02-check':[py,'scripts/aevora_h2_dv02_validation.py',str(output),'--repetitions','1','--strategy','buggy','--strategy','reference'],
      'db-init':[py,'-m','aevora','init'],
      'db-health':[py,'-c','from aevora.graph_repository import GraphRepository;r=GraphRepository.from_environment();print(r.state_fingerprint());r.close()'],
      'console-replay':[py,'-m','aevora_observatory.server','--replay-root',str(ROOT/'examples/observatory'),'--replay-sha256',pin,'--port',str(a.port)],
      'console-live':[py,'-m','aevora_observatory.server','--replay-root',str(ROOT/'examples/observatory'),'--replay-sha256',pin,'--port',str(a.port)],
      'mcp-config':[py,'examples/observatory/mcp_config.py'],
    }[a.command]
    if a.command=='test-core':output.mkdir(parents=True,exist_ok=False)
    # The readonly Console serves explicit request modes; LIVE errors never
    # select Replay. The command naming gives the documented starting mode.
    return subprocess.call([*args,*(['--'] if extra and a.command=='test-maintainer' else []),*extra],cwd=ROOT)
if __name__=='__main__':raise SystemExit(main())
