"""Own a fresh H4 database without touching H1/H2/H3 deployments or secrets."""
import json
import os
from pathlib import Path
import socket
import subprocess
from scripts.aevora_h4_audit import ROOT,archive,record,write,now


def main():
    a=archive();out=a/'g1/deployment';out.mkdir(parents=True,mode=0o700)
    h3=Path((ROOT/'aevora_validation/H3_CURRENT').read_text().strip());old=json.loads((h3/'CONFIG.json').read_text())
    private=Path.home()/'.config/aevora'/a.name
    code=record(out,'bootstrap',['python3',str(ROOT/'scripts/aevora_bootstrap.py'),str(private)])
    if code:raise ValueError('Private bootstrap failed')
    with socket.socket() as reserved:reserved.bind(('127.0.0.1',17692))
    project='aevora-h4-'+a.name.rsplit('-',1)[1]
    cfg={'runtime':old['runtime'],'password_file':str(private/'falkordb.password'),
         'redis_config_file':str(private/'falkordb.conf'),'port':17692,'graph':'aevora_h4_'+a.name.rsplit('-',1)[1],
         'compose_project':project,'source':'NEW_OWNED_EMPTY_VOLUME','at':now()}
    write(a/'CONFIG.json',cfg)
    env={'AEVORA_DB_PORT':str(cfg['port']),'AEVORA_FALKORDB_PASSWORD_FILE':cfg['password_file'],
         'AEVORA_REDIS_CONFIG_FILE':cfg['redis_config_file']}
    argv=['env',*[k+'='+v for k,v in env.items()],'docker','compose','-p',project,'-f',str(ROOT/'examples/observatory/deploy/compose.yaml'),'up','-d','--wait']
    code=record(out,'compose-empty-volume',argv)
    if code:raise ValueError('Fresh product deployment failed; receipts preserved')
    inspect=subprocess.run(['docker','image','inspect','falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62','--format','{{json .RepoDigests}}'],capture_output=True,text=True)
    if inspect.returncode:raise ValueError('Image fingerprint unavailable')
    write(out/'DEPLOYMENT.json',{'status':'AVAILABLE','project':project,'port':cfg['port'],
        'image_repo_digests':json.loads(inspect.stdout),'new_named_volume':True,'secrets_archived':False,
        'h1_h2_h3_untouched':True,'at':now()})
    print(json.dumps({'status':'AVAILABLE','project':project,'port':cfg['port'],'new_empty_volume':True}));return 0


if __name__=='__main__':raise SystemExit(main())
