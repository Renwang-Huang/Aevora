"""Real H3 RDB cold restore in a fresh owned Volume/port; no source destruction."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from scripts.aevora_h3_audit import archive,launch,record,write,digest,now


def sdk(operation,out,port=None):
    from aevora.graph_repository import GraphRepository
    from aevora.checkpoint import capture_graph,save_boundary,publish_checkpoint,verify_restored
    from aevora.models import LIFECYCLE_SCHEMA_VERSION
    repo=GraphRepository.from_environment()
    try:
        if operation=='save':
            value=save_boundary(repo,writers_quiesced=True,schema_version=LIFECYCLE_SCHEMA_VERSION)
            write(out/'SAVE_BOUNDARY.json',value)
        elif operation=='publish':
            boundary=json.loads((out/'SAVE_BOUNDARY.json').read_text())
            (out/'checkpoints').mkdir(mode=0o700)
            value=publish_checkpoint(out/'source-dump.rdb',out/'checkpoints',boundary,
                capture_graph(repo,schema_version=LIFECYCLE_SCHEMA_VERSION),
                image_digest=json.loads((out/'DEPLOYMENT.json').read_text())['image_digest'],writers_quiesced=True)
            write(out/'CHECKPOINT.json',value)
        else:
            checkpoint=json.loads((out/'CHECKPOINT.json').read_text())
            value=verify_restored(repo,Path(checkpoint['checkpoint_dir']),checkpoint['manifest_sha256'])
            write(out/'RESTORED_GRAPH.json',value)
        print(json.dumps(value if operation=='verify' else {'status':'COMPLETED','operation':operation}));return 0
    finally:repo.close()


def main(label):
    A=archive();out=A/'g1/recovery'/label;out.mkdir(parents=True,mode=0o700)
    # Every native writer must have finished before actual SAVE/publication.
    if any(list((A/gate).glob('**/runs/*/codex_events.pending')) for gate in ('g1','g2','g3')):
        raise ValueError('Native writer still active')
    config=json.loads((A/'CONFIG.json').read_text());compose=json.loads((A/'g0/compose.json').read_text())
    project='aevora-h3-restore-'+uuid.uuid4().hex[:12];container=project+'-graph-1'
    source=config['project']+'-graph-1';image=compose['services']['graph']['image']
    def command(name,argv):
        code=record(A,'g1-recovery-'+label+'-'+name,argv)
        if code:raise ValueError('Recovery command failed; raw receipt retained: '+name)
    inspect=subprocess.run(['docker','inspect','--format','{{json .Mounts}}',source],capture_output=True,text=True,timeout=30)
    if inspect.returncode:raise ValueError('Owned source inspection failed')
    mounts=json.loads(inspect.stdout);data=[m for m in mounts if m['Destination']=='/data']
    if len(data)!=1 or data[0]['Type']!='volume' or not data[0]['Name'].startswith(config['project']+'_'):
        raise ValueError('Source is not the independently owned H3 Volume')
    write(out/'DEPLOYMENT.json',{'source':source,'source_mounts':mounts,'image':image,
        'image_digest':image.split('@')[1],'target_project':project,'target_container':container,
        'source_port':17689,'target_port':17690,'classification':'Cold restore, last completed SAVE RPO only'})
    command('save',launch('-m','scripts.aevora_h3_recovery','sdk','save',out))
    command('copy-rdb',['docker','cp',source+':/data/dump.rdb',str(out/'source-dump.rdb')])
    (out/'source-dump.rdb').chmod(0o600)
    command('publish',launch('-m','scripts.aevora_h3_recovery','sdk','publish',out))
    checkpoint=json.loads((out/'CHECKPOINT.json').read_text())
    target=copy.deepcopy(compose);target['name']=project;target['services']['graph']['ports']=['127.0.0.1:17690:6379']
    target['services']['graph']['restart']='no'
    (out/'compose.json').write_text(json.dumps(target,indent=2)+'\n')
    prefix=['docker','compose','-f',str(out/'compose.json'),'-p',project]
    command('create',prefix+['create'])
    command('stage',['docker','cp',str(Path(checkpoint['checkpoint_dir'])/'dump.rdb'),container+':/data/dump.rdb'])
    command('start',prefix+['up','-d','--wait','--wait-timeout','60'])
    argv=launch('-m','scripts.aevora_h3_recovery','sdk','verify',out)
    argv=[('AEVORA_FALKORDB_PORT=17690' if x=='AEVORA_FALKORDB_PORT=17689' else x) for x in argv]
    command('verify',argv)
    # Target remains running for a separately new native readback if needed.
    write(out/'RESULT.json',{'status':'PASS','target_project':project,'target_port':17690,
        'checkpoint_sha256':checkpoint['manifest_sha256'],'restored_graph_sha256':digest(out/'RESTORED_GRAPH.json'),
        'rdb_sha256':digest(out/'source-dump.rdb'),'source_volume_untouched':data[0]['Name'],
        'RPO':'Only last completed SAVE','native_session':'NOT_EXECUTED_BY_THIS_OFFLINE_CONTROLLER','recorded_at':now()})
    print(json.dumps({'status':'PASS','target_port':17690,'target_project':project}));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='op',required=True)
    q=s.add_parser('run');q.add_argument('--label',required=True)
    q=s.add_parser('sdk');q.add_argument('operation',choices=['save','publish','verify']);q.add_argument('output',type=Path)
    a=p.parse_args();raise SystemExit(main(a.label) if a.op=='run' else sdk(a.operation,a.output))
