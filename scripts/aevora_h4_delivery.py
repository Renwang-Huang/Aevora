"""H4 stopped delivery, real byte scans and immutable history verification.

Host-only validation. Secret values and individual hashes never leave memory.
All original failed commands and the explicitly stopped incomplete attempt stay.
"""
import argparse,hashlib,json,os,shutil,stat,tarfile,zipfile
from pathlib import Path
from scripts.aevora_h4_audit import ROOT,archive,sources,write,digest,now
from scripts.aevora_h3_delivery import ordinary

def patterns(A):
    configs=[json.loads((A/'CONFIG.json').read_text()),json.loads((A/'g5/fresh-user-01/CONFIG.json').read_text())]
    paths=[Path(c['password_file']) for c in configs]+[Path(os.environ.get('ORDERFLOW_GATEWAY_SECRET_PATH', str(Path.home()/'.config/orderflow/gateway_api_key')))]
    result=[]
    for p in paths:
        s=p.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077:raise ValueError('Actual host secret permission invalid')
        secret=p.read_bytes().strip()
        if len(secret)<16:raise ValueError('Actual configured secret unavailable')
        result.extend([secret,hashlib.sha256(secret).digest(),hashlib.sha256(secret).hexdigest().encode(),hashlib.sha256(secret).hexdigest().upper().encode()])
    return result,len(paths)

def scan_stream(stream,needles):
    tail=b'';total=0;found=False;overlap=max(map(len,needles))-1
    while block:=stream.read(1024*1024):
        data=tail+block;total+=len(block);found=found or any(p in data for p in needles);tail=data[-overlap:]
    return total,found

def public_scan(A,label='public-safety'):
    final=label=='public-safety-final'
    out=A/'g5'/label;out.mkdir(mode=0o700);needles,classes=patterns(A);product=A/('g5/public-product-final' if final else 'g5/public-product-02')
    private={digest(p) for folder in ['evaluator/hidden_tests','evaluator/private_manifests','evaluator/reference_patches','evaluator/private_labels'] for p in (ROOT/folder).rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size>32 and '__pycache__' not in p.parts}
    hits=[];bad=[];count=0;total=0
    def inspect(name,data):
        nonlocal total,count
        count+=1;total+=len(data)
        if any(p in data for p in needles):hits.append(name)
        if hashlib.sha256(data).hexdigest() in private:bad.append(name)
    forbidden={'benchmark','evaluator','integrations','reference_patches','hidden_tests','private_manifests','private_labels'}
    members=[]
    for p in sorted((product/'source').rglob('*')):
        if not p.is_file() or p.is_symlink() or set(p.relative_to(product/'source').parts)&{'.git','build','dist','__pycache__'} or any(part.endswith('.egg-info') for part in p.parts):continue
        name=str(p.relative_to(product));members.append(name)
        if set(p.relative_to(product/'source').parts)&forbidden:bad.append(name)
        inspect(name,p.read_bytes())
    for p in [product/'aevora-h4-public-source.zip',*sorted((product/'dist').iterdir())]:
        if p.suffix in {'.zip','.whl'}:
            with zipfile.ZipFile(p) as z:
                for member in z.infolist():
                    if member.is_dir():continue
                    name=p.name+'!'+member.filename
                    if set(Path(member.filename).parts)&forbidden:bad.append(name)
                    inspect(name,z.read(member))
        else:
            with tarfile.open(p,'r:*') as t:
                for member in t:
                    if member.isfile():
                        if set(Path(member.name).parts)&forbidden:bad.append(p.name+'!'+member.name)
                        inspect(p.name+'!'+member.name,t.extractfile(member).read())
    image=A/('g5/public-image-final/aevora-h4-image.tar' if final else 'g5/public-image/aevora-h4-image.tar')
    with tarfile.open(image,'r:*') as saved:
        for layer in saved:
            if not layer.isfile():continue
            stream=saved.extractfile(layer)
            if layer.name.endswith('.tar') or '/blobs/' in '/'+layer.name:
                try:
                    with tarfile.open(fileobj=stream,mode='r|*') as contents:
                        for member in contents:
                            if not member.isfile():continue
                            name=layer.name+'!'+member.name;parts=set(Path(member.name).parts)
                            if parts&forbidden or parts&{'grant.json','gateway.key','falkordb.password'}:bad.append(name)
                            n,hit=scan_stream(contents.extractfile(member),needles);count+=1;total+=n
                            if hit:hits.append(name)
                except tarfile.ReadError:
                    # Registry manifests/config blobs are scanned separately;
                    # an actual tar layer remains streaming bounded.
                    stream=saved.extractfile(layer);n,hit=scan_stream(stream,needles);count+=1;total+=n
                    if hit:hits.append(layer.name)
            else:
                n,hit=scan_stream(stream,needles);count+=1;total+=n
                if hit:hits.append(layer.name)
    for p in (A/('g5/public-image-browser-final' if final else 'g5/public-image-browser-01')).glob('*.json'):inspect('actual_browser_http/'+p.name,p.read_bytes())
    result={'status':'PASS' if not hits and not bad else 'FAIL','secret_or_individual_hash_matches':hits,'private_source_path_or_exact_copy_matches':sorted(set(bad)),'actual_secret_classes':classes,'uncompressed_bytes_scanned':total,'members_scanned':count,'image_tar_sha256':digest(image),'source_zip_sha256':digest(product/'aevora-h4-public-source.zip'),'secret_values_or_individual_hashes_emitted':False,'scope':'Public source/package distributions, real Docker filesystem layers, frontend and actual browser HTTP JSON; no hostile kernel isolation claim','at':now()}
    write(out/'RESULT.json',result);print(json.dumps(result));return 0 if result['status']=='PASS' else 1

def history(A,label='history-preservation'):
    out=A/'g5'/label;out.mkdir(mode=0o700);checks=[]
    for name in ['PROTECTED_HISTORY.json','INHERITED_TEST_SOURCES.json','FROZEN_TASK_TRUTH.json','HISTORICAL_ROOT_REPORTS_PROTECTED.json']:
        source=A/'g0'/name
        if not source.exists():source=A/name
        indexed=json.loads(source.read_text());indexed=indexed.get('files',indexed);bad=[]
        for rel,row in indexed.items():
            expected=row['sha256'] if isinstance(row,dict) else row;p=ROOT/rel
            if not p.is_file() or p.is_symlink() or digest(p)!=expected:bad.append(rel)
        checks.append({'source':str(source.relative_to(A)),'index_sha256':digest(source),'files_checked':len(indexed),'mismatches':bad,'status':'FAIL' if bad else 'PASS'})
    result={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'at':now()};write(out/'RESULT.json',result);print(json.dumps(result));return 0 if result['status']=='PASS' else 1

def stopped(A):
    if (A/'EVIDENCE_MANIFEST.json').exists():raise ValueError('Full already sealed')
    for p in (A/'jobs').glob('*/START.json'):
        v=json.loads(p.read_text());proc=Path('/proc')/str(v['pid'])/'stat'
        if proc.exists():
            fields=proc.read_text().rsplit(')',1)[1].split()
            if fields[19]==v['proc_start_ticks'] and fields[0]!='Z':raise ValueError('Owned evidence writer still active: '+p.parent.name)
    pending=list(A.glob('**/codex_events.pending'))
    qualification=json.loads((A/'g4/STOPPED_ATTEMPT_01_NATIVE_RECOVERY.json').read_text())
    if qualification.get('classification')!='INCOMPLETE_COLLECTION' or qualification.get('terminal_exit')!='UNAVAILABLE' or qualification.get('ephemeral_state_removed') is not True or qualification.get('raw_pending_files_preserved') is not True:
        raise ValueError('Stopped attempt qualification absent')
    if any('ordinary_repair_01' not in p.parts for p in pending):raise ValueError('Unqualified native pending writer')
    return pending

def snapshot(A,label='original'):
    suffix='' if label=='original' else '_'+label
    stopped(A);out=A/('final/source_snapshot'+suffix);out.mkdir(parents=True,mode=0o700);rows=sources()
    for rel,row in rows.items():
        p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p);p.chmod(row['mode'])
        if digest(p)!=row['sha256']:raise ValueError('Source changed during snapshot')
    write(A/('final/DELIVERY_SOURCE_MANIFEST'+suffix+'.json'),{'files':rows,'snapshot':str(out.relative_to(A)),'at':now(),'qualification':'Current delivery source; each native Session retains its original separate admitted source epoch'})
    commands={}
    for p in A.rglob('command*.json'):
        if set(p.parts)&{'venv','frozen_source_snapshot','source'} or any(part.startswith('source_snapshot') for part in p.parts):continue
        try:v=json.loads(p.read_text())
        except (ValueError,UnicodeError):continue
        if isinstance(v.get('argv'),list) and type(v.get('exit_code')) is int:commands[str(p.relative_to(A))]={'argv':v['argv'],'exit_code':v['exit_code'],'sha256':digest(p)}
    write(A/('final/COMMAND_INDEX'+suffix+'.json'),{'commands':commands,'at':now(),'qualification':'Actual completed commands include expected failure/denial, no grade upgrades'})
    print(json.dumps({'status':'PASS','source_files':len(rows),'commands':len(commands)}))

def scan(A,label='original'):
    stopped(A);needles,classes=patterns(A);hits=[];total=0;files,links=ordinary(A)
    for p in files:
        with p.open('rb') as stream:n,hit=scan_stream(stream,needles)
        total+=n
        if hit:hits.append(str(p.relative_to(A)))
    suffix='' if label=='original' else '_'+label
    result={'status':'FAIL' if hits else 'PASS','ordinary_files':len(files),'bytes_scanned':total,'actual_secret_classes':classes,'secret_or_individual_hash_matches':hits,'symlink_targets_not_read':len(links),'secret_values_or_individual_hashes_emitted':False,'at':now()};write(A/('final/SECRET_SCAN'+suffix+'.json'),result);print(json.dumps(result));return 0 if not hits else 1

def seal(A,label='original'):
    pending=stopped(A)
    suffix='' if label=='original' else '_'+label
    if json.loads((A/('final/SECRET_SCAN'+suffix+'.json')).read_text())['status']!='PASS':raise ValueError('Actual full secret gate required')
    files,links=ordinary(A);rows={str(p.relative_to(A)):digest(p) for p in files}
    result={'kind':'AEVORA_H4_FULL_ARCHIVE','ordinary_files_sha256':dict(sorted(rows.items())),'ordinary_file_count':len(rows),'total_bytes':sum(p.stat().st_size for p in files),'symlinks_metadata_only':links,'sealed_at':now(),'excluded_self_outputs':['EVIDENCE_MANIFEST.json','SHA256SUMS'],'qualified_stopped_incomplete_pending_files':[str(p.relative_to(A)) for p in pending],'qualification':'Actual stopped bytes, local hashes, no external attestation. Incomplete attempt is retained, never promoted. Final export and delivery receipts are outside Full.'};write(A/'EVIDENCE_MANIFEST.json',result)
    with (A/'SHA256SUMS').open('x') as f:
        for rel,h in sorted(rows.items()):f.write(h+'  '+rel+'\n')
        f.write(digest(A/'EVIDENCE_MANIFEST.json')+'  EVIDENCE_MANIFEST.json\n')
    print(json.dumps({'status':'PASS','ordinary_files':len(rows),'total_bytes':result['total_bytes'],'manifest_sha256':digest(A/'EVIDENCE_MANIFEST.json'),'checksums_sha256':digest(A/'SHA256SUMS')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('op',choices=['public-scan','history','snapshot','scan','seal']);p.add_argument('--label',default=None);a=p.parse_args()
    if a.label is None:a.label={'history':'history-preservation','public-scan':'public-safety'}.get(a.op,'original')
    if not a.label.replace('-','').isalnum():raise ValueError('Simple evidence label required')
    raise SystemExit(history(archive(),a.label) if a.op=='history' else public_scan(archive(),a.label) if a.op=='public-scan' else {'snapshot':snapshot,'scan':scan,'seal':seal}[a.op](archive(),a.label) or 0)
