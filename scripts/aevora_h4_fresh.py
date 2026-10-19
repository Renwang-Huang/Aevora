"""Own a separate empty G5 Volume; public-only image, no historical mutation."""
import argparse,json,os,socket,uuid
from pathlib import Path
from scripts.aevora_h4_audit import ROOT,archive,record,write,now

def main(label):
    A=archive();out=A/'g5'/label;out.mkdir(mode=0o700);product=A/'g5/public-product-02/source'
    if not product.is_dir():raise ValueError('Built explicit public source required')
    private=Path.home()/'.config/aevora'/('h4-fresh-'+uuid.uuid4().hex)
    assert record(A,label+'-bootstrap',['python3',str(product/'scripts/aevora_bootstrap.py'),str(private)])==0
    with socket.socket() as s:s.bind(('127.0.0.1',17693))
    cfg={'port':17693,'graph':'aevora_product','password_file':str(private/'falkordb.password'),'redis_config_file':str(private/'falkordb.conf'),'compose_project':'aevora-h4-fresh-'+uuid.uuid4().hex[:12],'public_source':str(product),'source':'NEW_EMPTY_VOLUME','at':now()};write(out/'CONFIG.json',cfg)
    env=['AEVORA_DB_PORT=17693','AEVORA_FALKORDB_PASSWORD_FILE='+cfg['password_file'],'AEVORA_REDIS_CONFIG_FILE='+cfg['redis_config_file']]
    assert record(A,label+'-compose-up',['env',*env,'docker','compose','-p',cfg['compose_project'],'-f',str(product/'h4/deploy/compose.yaml'),'up','-d','--wait'])==0
    write(A/'g5/FRESH_CURRENT.json',{'config':str((out/'CONFIG.json').relative_to(A)),'at':now()});print(json.dumps({'status':'READY','port':17693,'new_volume':True}));return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);args=p.parse_args();raise SystemExit(main(args.label))
