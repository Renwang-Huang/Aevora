"""H3 final local source snapshot, secret-value scan and stopped Full sealing.

Reuses existing source selection and SHA/receipt protocols. Never reads linked
external files; secret values and their individual hashes are never emitted.
Seal invocation must be recorded outside Full, since its last output closes
the archive. Local consistency is not external attestation.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
from scripts.aevora_h3_audit import archive,ROOT,sources,digest,write,now


def ordinary(A):
    files=[];links=[]
    for current,dirs,names in os.walk(A,followlinks=False):
        for name in list(dirs):
            p=Path(current)/name
            if p.is_symlink():links.append({'path':str(p.relative_to(A)),'target':os.readlink(p),'scope':'Metadata only; target not read'});dirs.remove(name)
        dirs.sort()
        for name in sorted(names):
            p=Path(current)/name;info=p.lstat()
            if stat.S_ISLNK(info.st_mode):links.append({'path':str(p.relative_to(A)),'target':os.readlink(p),'scope':'Metadata only; target not read'})
            elif stat.S_ISREG(info.st_mode):files.append(p)
            else:raise ValueError('Special archive member refused: '+str(p.relative_to(A)))
    return files,links


def stopped(A):
    if list(A.glob('**/codex_events.pending')):raise ValueError('Native writer active')
    if (A/'EVIDENCE_MANIFEST.json').exists():raise ValueError('Full already sealed')


def snapshot(A):
    stopped(A);out=A/'final/source_snapshot';out.mkdir(mode=0o700)
    rows=sources()
    for rel,row in rows.items():
        dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest);dest.chmod(row['mode'])
        if digest(dest)!=row['sha256']:raise ValueError('Current source changed during snapshot')
    write(A/'final/DELIVERY_SOURCE_MANIFEST.json',{'files':rows,'recorded_at':now(),'qualification':'Post-live delivery source; never retroactively attributed to native Session epochs','root_index_staged':False})
    commands={}
    for p in A.glob('**/command*.json'):
        if any(part in {'venv','source_snapshot','frozen_source_snapshot','clean-checkout','clone'} for part in p.relative_to(A).parts):continue
        try:v=json.loads(p.read_text())
        except (ValueError,UnicodeError):continue
        if isinstance(v.get('argv'),list) and isinstance(v.get('exit_code'),int):
            commands[str(p.relative_to(A))]={'argv':v['argv'],'exit_code':v['exit_code'],'command_sha256':digest(p),'qualification':'Actual command exit; expected FAIL/ERROR/denial is not a successful engineering submission'}
    write(A/'final/COMMAND_INDEX.json',{'commands':commands,'recorded_at':now(),'index_scope':'Actual completed command receipts before final scan/seal/export; outside-Full receipts are linked separately'})
    print(json.dumps({'status':'PASS','source_files':len(rows),'commands':len(commands)}))


def scan(A):
    stopped(A);cfg=json.loads((A/'CONFIG.json').read_text())
    paths=[('graph_host_secret',Path(cfg['password_file'])),('model_host_secret',Path(os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH', str(Path.home()/'.config/orderflow/gateway_api_key'))))]
    secrets=[]
    for label,path in paths:
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Host credential permissions invalid')
        value=path.read_bytes().strip()
        if len(value)<16:raise ValueError('Credential scan requires actual bounded configured secret')
        secrets.append((label,value))
    hits=[];total=0;files,links=ordinary(A);overlap=max(len(v) for _,v in secrets)-1
    for path in files:
        tail=b''
        with path.open('rb') as f:
            while block:=f.read(1024*1024):
                total+=len(block);data=tail+block
                for label,value in secrets:
                    if value in data:hits.append({'path':str(path.relative_to(A)),'credential_class':label})
                tail=data[-overlap:]
    result={'status':'PASS' if not hits else 'FAIL','ordinary_files':len(files),'bytes_scanned':total,'exact_actual_secret_classes':len(secrets),'matches':hits,'linked_targets_not_read':len(links),'secret_values_archived':False,'individual_secret_hashes_archived':False,'recorded_at':now()}
    write(A/'final/SECRET_SCAN.json',result);print(json.dumps(result));return 0 if not hits else 1


def seal(A):
    stopped(A)
    if json.loads((A/'final/SECRET_SCAN.json').read_text())['status']!='PASS':raise ValueError('Secret gate required')
    files,links=ordinary(A);rows={};total=0
    for p in files:
        rel=str(p.relative_to(A))
        if rel in {'EVIDENCE_MANIFEST.json','SHA256SUMS'}:raise ValueError('Unexpected pre-existing seal output')
        rows[rel]=digest(p);total+=p.stat().st_size
    result={'kind':'AEVORA_H3_FULL_ARCHIVE','ordinary_files_sha256':dict(sorted(rows.items())),'total_bytes':total,'ordinary_file_count':len(rows),'symlinks_metadata_only':links,'sealed_at':now(),'excluded_self_outputs':['EVIDENCE_MANIFEST.json','SHA256SUMS'],'qualification':'Local actual file hashes; stopped writers; no third-party attestation. Final export/verify/delivery receipts live outside this immutable archive.'}
    write(A/'EVIDENCE_MANIFEST.json',result)
    with (A/'SHA256SUMS').open('x') as f:
        for rel,h in sorted(rows.items()):f.write(h+'  '+rel+'\n')
        f.write(digest(A/'EVIDENCE_MANIFEST.json')+'  EVIDENCE_MANIFEST.json\n')
    print(json.dumps({'status':'PASS','ordinary_files':len(rows),'total_bytes':total,'manifest_sha256':digest(A/'EVIDENCE_MANIFEST.json'),'checksums_sha256':digest(A/'SHA256SUMS')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['snapshot','scan','seal']);args=p.parse_args()
    op={'snapshot':snapshot,'scan':scan,'seal':seal}[args.operation];raise SystemExit(op(archive()) or 0)
