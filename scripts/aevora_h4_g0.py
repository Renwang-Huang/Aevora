"""Actual H4-G0 negative controls, deterministic projection and disclosure scan."""
from pathlib import Path
import argparse
from hashlib import sha256
import json
import os
import shutil
from scripts.aevora_h4_audit import archive,ROOT,digest,write,record


def negative():
    a=archive();out=a/'g0/semantic-negative-controls';out.mkdir(mode=0o700)
    results=[]
    cases=[('run-mismatch',None,lambda c:c['acts'][0].update(run_id='forged-run')),
           ('outcome-mismatch','origin',lambda c:c.update(outcome_id='orderflow:forged')),
           ('edge-endpoint-mismatch','evolution',lambda c:c['selected_edge'].update(target='orderflow:wrong'))]
    for label,artifact,change in cases:
        dest=out/label;dest.mkdir();shutil.copytree(ROOT/'h4/replay',dest/'replay')
        contract=json.loads((ROOT/'h4/hero_scenario_contract.json').read_text())
        if artifact:
            p=dest/contract['artifacts'][artifact]['artifact_path'];value=json.loads(p.read_text());change(value)
            p.write_text(json.dumps(value,sort_keys=True)+'\n');contract['artifacts'][artifact]['sha256']=digest(p)
        else:change(contract)
        write(dest/'hero_scenario_contract.json',contract)
        pin=digest(dest/'hero_scenario_contract.json')
        code=record(out,label+'-command',['python3','-I',str(ROOT/'h4/verify_hero.py'),str(dest),'--sha256',pin])
        results.append({'control':label,'actual_exit':code,'expected_exit':1,'status':'PASS' if code==1 else 'FAIL',
                        'contract_sha256':pin,'qualification':'Semantic mutation; artifact hash and supplied contract pin recomputed, so rejection is not just byte mismatch.'})
    result={'status':'PASS' if all(r['status']=='PASS' for r in results) else 'FAIL','checks':results}
    write(out/'RESULT.json',result);print(json.dumps(result));return 0 if result['status']=='PASS' else 1


def repeat():
    from scripts.aevora_h4_hero import build
    a=archive();dest=a/'g0/repeat-public-projection'
    build(dest,'hero-repeat')
    paths=['hero_scenario_contract.json',*[str(p.relative_to(ROOT/'h4')) for p in sorted((ROOT/'h4/replay').glob('*.json'))]]
    rows=[{'path':p,'original_sha256':digest(ROOT/'h4'/p),'repeat_sha256':digest(dest/p)} for p in paths]
    result={'status':'PASS' if all(x['original_sha256']==x['repeat_sha256'] for x in rows) else 'FAIL','files':rows,'scope':'Exact repeated projection bytes; no timestamp normalization or historical change'}
    write(a/'g0/PROJECTION_REPEATABILITY.json',result);print(json.dumps({'status':result['status'],'files':len(rows)}));return 0 if result['status']=='PASS' else 1


def scan():
    a=archive();h3=Path((ROOT/'aevora_validation/H3_CURRENT').read_text().strip());cfg=json.loads((h3/'CONFIG.json').read_text())
    secret_paths=[Path(cfg['password_file']),Path(os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH', str(Path.home()/'.config/orderflow/gateway_api_key')))]
    patterns=[]
    for p in secret_paths:
        info=p.lstat()
        if p.is_symlink() or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1:raise ValueError('Host-only credential permissions invalid')
        value=p.read_bytes().strip()
        if len(value)<16:raise ValueError('Actual bounded credential required for value scan')
        patterns.extend([value,sha256(value).hexdigest().encode(),sha256(value).hexdigest().upper().encode(),sha256(value).digest()])
    files=[ROOT/'h4/hero_scenario_contract.json',*sorted((ROOT/'h4/replay').glob('*.json'))]
    hits=[]
    for p in files:
        data=p.read_bytes()
        if any(s in data for s in patterns):hits.append({'path':str(p.relative_to(ROOT)),'class':'ACTUAL_CREDENTIAL_OR_INDIVIDUAL_DIGEST'})
        if any(s in data for s in [b'evaluator/hidden_tests/',b'evaluator/reference_patches/',b'/home/private-user/.config/',b'Bearer ',b'sk-cpamp-']):hits.append({'path':str(p.relative_to(ROOT)),'class':'PRIVATE_PATH_OR_CREDENTIAL_PATTERN'})
    result={'status':'PASS' if not hits else 'FAIL','public_files':len(files),'matches':hits,'actual_credential_classes':len(secret_paths),'secret_value_or_individual_hash_archived':False,'raw_logs_included':False}
    write(a/'g0/PUBLIC_PROJECTION_SCAN.json',result);print(json.dumps(result));return 0 if not hits else 1


def frozen():
    a=archive();old=Path((ROOT/'aevora_validation/H3_CURRENT').read_text().strip())
    manifest=json.loads((old/'EVIDENCE_MANIFEST.json').read_text());rows=manifest['ordinary_files_sha256']
    bad=[p for p,h in rows.items() if digest(old/p)!=h]
    result={'status':'PASS' if not bad else 'FAIL','checked_h3_sealed_files':len(rows),'mismatches':bad,'qualification':'Actual current byte hashes; H3 scores not re-run or changed'}
    write(a/'g0/H3_FULL_REHASH.json',result);print(json.dumps(result));return 0 if not bad else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=['negative','repeat','scan','frozen']);a=p.parse_args()
    raise SystemExit({'negative':negative,'repeat':repeat,'scan':scan,'frozen':frozen}[a.op]())
