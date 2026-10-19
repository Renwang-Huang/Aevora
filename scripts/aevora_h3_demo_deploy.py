"""Fresh H3-demo deployment from a new trusted SAVE/RDB, owned port17691.

Reuses Core's checkpoint publication/verification. Neither original H3 nor its
withdrawal-control replica is replaced. No model calls or secret byte archive.
"""
import copy
import json
from pathlib import Path
import subprocess
import uuid
from scripts.aevora_h3_audit import archive,write,launch,record,digest,now


def main():
    A=archive()
    if any(list((A/g).glob('**/runs/*/codex_events.pending')) for g in ['g1','g2','g3']):raise ValueError('Native writer active')
    out=A/'g4/demo-deployment';out.mkdir(parents=True,mode=0o700)
    cfg=json.loads((A/'CONFIG.json').read_text());original=json.loads((A/'g0/compose.json').read_text())
    project='aevora-h3-demo-'+uuid.uuid4().hex[:12];container=project+'-graph-1';source=cfg['project']+'-graph-1'
    inspected=subprocess.run(['docker','inspect','--format','{{json .Mounts}}',source],capture_output=True,text=True,timeout=30)
    if inspected.returncode:raise ValueError('Source ownership inspection failed')
    mounts=json.loads(inspected.stdout);data=[m for m in mounts if m['Destination']=='/data']
    if len(data)!=1 or data[0]['Type']!='volume' or not data[0]['Name'].startswith(cfg['project']+'_'):raise ValueError('Owned H3 source Volume required')
    image=original['services']['graph']['image'];actual=subprocess.run(['docker','image','inspect','--format','{{json .RepoDigests}}',image],capture_output=True,text=True,timeout=30)
    if actual.returncode or not any(value.split('@')[-1]==image.split('@')[-1] for value in json.loads(actual.stdout)):
        raise ValueError('Actually inspected pinned image digest mismatch')
    write(out/'DEPLOYMENT.json',{'source':source,'source_volume':data[0]['Name'],'target_project':project,'target_container':container,
         'source_port':17689,'target_port':17691,'image_digest':image.split('@')[1],'actual_repo_digests':json.loads(actual.stdout),'at':now()})
    def cmd(label,argv):
        if record(A,'g4-demo-deploy-'+label,argv):raise ValueError('Fresh demo deploy failed: '+label)
    cmd('save',launch('-m','scripts.aevora_h3_recovery','sdk','save',out))
    cmd('copy',['docker','cp',source+':/data/dump.rdb',str(out/'source-dump.rdb')]);(out/'source-dump.rdb').chmod(0o600)
    cmd('publish',launch('-m','scripts.aevora_h3_recovery','sdk','publish',out))
    checkpoint=json.loads((out/'CHECKPOINT.json').read_text());target=copy.deepcopy(original);target['name']=project
    target['services']['graph']['ports']=['127.0.0.1:17691:6379'];target['services']['graph']['restart']='no'
    write(out/'compose.json',target);prefix=['docker','compose','-f',str(out/'compose.json'),'-p',project]
    cmd('create',prefix+['create']);cmd('stage',['docker','cp',str(Path(checkpoint['checkpoint_dir'])/'dump.rdb'),container+':/data/dump.rdb'])
    cmd('start',prefix+['up','-d','--wait','--wait-timeout','60'])
    argv=launch('-m','scripts.aevora_h3_recovery','sdk','verify',out)
    argv=[x.replace('AEVORA_FALKORDB_PORT=17689','AEVORA_FALKORDB_PORT=17691') for x in argv];cmd('verify',argv)
    write(out/'RESULT.json',{'status':'PASS','target_port':17691,'project':project,'rdb_sha256':digest(out/'source-dump.rdb'),
       'checkpoint_manifest_sha256':checkpoint['manifest_sha256'],'restored_graph_sha256':checkpoint['graph_sha256'],'RPO':'Last completed SAVE only','at':now()})
    print(json.dumps({'status':'PASS','new_demo_port':17691}));return 0


if __name__=='__main__':raise SystemExit(main())
