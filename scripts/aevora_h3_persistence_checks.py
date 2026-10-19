"""After-withdrawal restart and actual unavailable-database control, owned replica only."""
import argparse
import json
import os
import socket
import subprocess
from scripts.aevora_h3_audit import archive,write,record,launch,digest,now


def sdk(output,operation):
    from aevora.graph_repository import GraphRepository
    from aevora.models import GraphUnavailable,LIFECYCLE_SCHEMA_VERSION
    from aevora.checkpoint import capture_graph
    if os.environ['AEVORA_FALKORDB_PORT']!='17690':raise ValueError('Owned cold replica only')
    A=archive()
    if operation=='unavailable':
        try:
            repo=GraphRepository.from_environment()
            try:repo.experience_ids()
            finally:repo.close()
        except GraphUnavailable as e:
            write(output/'DISCONNECTED.json',{'status':'PASS','actual_error_type':type(e).__name__,'static_fallback':False,'cached_answer':False,'port':17690});return 0
        raise ValueError('Disconnected database unexpectedly returned data')
    actual=capture_graph(GraphRepository.from_environment(),schema_version=LIFECYCLE_SCHEMA_VERSION)
    expected=json.loads((A/'g1/graph-checks/lifecycle_01/AFTER.json').read_text())
    if actual!=expected:raise ValueError('Candidate lifecycle/graph changed over actual restart')
    write(output/'RESTARTED_GRAPH.json',actual)
    write(output/'RESULT.json',{'status':'PASS','graph_sha256':actual['graph_sha256'],'at':now(),
       'scope':'All Candidate events, pending/rejected and withdrawn states, source links and old QuerySnapshot survived actual SAVE/restart; cold replica17690 only.'})
    return 0


def main():
    A=archive();out=A/'g1/persistence-controls';out.mkdir(mode=0o700)
    deployment=json.loads((A/'g1/recovery/lifecycle_02/DEPLOYMENT.json').read_text());container=deployment['target_container']
    if not container.startswith('aevora-h3-restore-') or deployment['target_port']!=17690:raise ValueError('Unknown container')
    def command(label,argv):
        code=record(A,'g1-persistence-'+label,argv)
        if code:raise ValueError('Persistence command failed: '+label)
    argv=launch('-m','scripts.aevora_h3_persistence_checks','sdk',str(out),'unavailable')
    argv=[x.replace('AEVORA_FALKORDB_PORT=17689','AEVORA_FALKORDB_PORT=17690') for x in argv]
    command('stop',['docker','stop',container])
    try:
        with socket.socket() as owned:
            owned.bind(('127.0.0.1',17690))
            command('disconnected',argv)
    finally:command('start',['docker','start',container])
    health=subprocess.run(['docker','inspect','--format','{{.State.Health.Status}}',container],capture_output=True,text=True)
    # The SDK's connection has its own bounded timeout; startup is a finite
    # infrastructure check, not a wall-clock limit on a healthy Agent.
    import time
    deadline=time.monotonic()+30
    while health.stdout.strip()!='healthy' and time.monotonic()<deadline:
        time.sleep(.1);health=subprocess.run(['docker','inspect','--format','{{.State.Health.Status}}',container],capture_output=True,text=True)
    if health.returncode or health.stdout.strip()!='healthy':raise ValueError('Cold replica health not restored')
    argv=launch('-m','scripts.aevora_h3_persistence_checks','sdk',str(out),'restart')
    argv=[x.replace('AEVORA_FALKORDB_PORT=17689','AEVORA_FALKORDB_PORT=17690') for x in argv]
    command('verify',argv);return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True);s.add_parser('run')
    q=s.add_parser('sdk');q.add_argument('output',type=__import__('pathlib').Path);q.add_argument('operation')
    a=p.parse_args();raise SystemExit(main() if a.op=='run' else sdk(a.output,a.operation))
