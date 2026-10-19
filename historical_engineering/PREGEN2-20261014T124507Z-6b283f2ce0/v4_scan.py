"""Trusted member/byte scan; known secret values/hashes remain only in memory."""
from pathlib import Path
import hashlib,io,json,os,stat,tarfile,zipfile
from runtime import E,W,R,C,write,sha,now
configs=[json.loads((E/'RUNTIME_CONFIG.json').read_text()),json.loads((Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch/orderflow_incident_lab/aevora_validation/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef')/'CONFIG.json').read_text()),json.loads((Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_archive/gen1_legacy/Gen1.5.2-approved-batch/orderflow_incident_lab/aevora_validation/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef')/'g5/fresh-user-01/CONFIG.json').read_text())]
secret_paths=[Path(c['password_file']) for c in configs]+[Path('/home/PRIVATE_MAINTAINER/.config/orderflow/gateway_api_key')]
needles=[];classes=0
for p in secret_paths:
    s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077
    b=p.read_bytes().strip();assert len(b)>=16
    needles += [b,hashlib.sha256(b).digest(),hashlib.sha256(b).hexdigest().encode(),hashlib.sha256(b).hexdigest().upper().encode()];classes+=1
private={sha(p) for folder in ['evaluator/hidden_tests','evaluator/private_manifests','evaluator/reference_patches','evaluator/private_labels','aevora_maintainer'] for p in (W/folder).rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size>32 and '__pycache__' not in p.parts}
bad=[];hits=[];count=0;total=0
forbidden={'benchmark','evaluator','integrations','aevora_maintainer','reference_patches','hidden_tests','private_manifests','private_labels','grant.json','gateway.key','falkordb.password','AGENTS.md'}
def inspect(name,data):
    global count,total
    count+=1;total+=len(data)
    if set(Path(name).parts)&forbidden or hashlib.sha256(data).hexdigest() in private:bad.append(name)
    if any(n in data for n in needles):hits.append(name)
def stream(name,file):
    global count,total
    count+=1;tail=b'';cache=bytearray();n=0;overlap=max(map(len,needles))-1
    if set(Path(name).parts)&forbidden:bad.append(name)
    while block:=file.read(1024*1024):
        n+=len(block);total+=len(block);data=tail+block
        if any(p in data for p in needles):hits.append(name)
        tail=data[-overlap:]
        if n<=8*1024*1024:cache.extend(block)
    if n<=8*1024*1024 and hashlib.sha256(cache).hexdigest() in private:bad.append(name)
product=E/'05_product/public-build-1';selection=json.loads((product/'PUBLIC_SELECTION.json').read_text())['files']
for rel in selection:inspect(rel,(product/'source'/rel).read_bytes())
for p in [product/'aevora-gen15-public-source.zip',*sorted((product/'dist').iterdir())]:
    if p.suffix in {'.zip','.whl'}:
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if not n.endswith('/'):inspect(p.name+'/'+n,z.read(n))
    else:
        with tarfile.open(p) as t:
            for m in t:
                if m.isfile():stream(p.name+'/'+m.name,t.extractfile(m))
image=E/'05_product/public_image_staged2.tar'
with tarfile.open(image) as t:
    for m in t:
        if not m.isfile():continue
        f=t.extractfile(m)
        try:
            with tarfile.open(fileobj=f,mode='r|*') as layers:
                for child in layers:
                    if child.isfile():stream(m.name+'/'+child.name,layers.extractfile(child))
        except tarfile.ReadError:stream(m.name,t.extractfile(m))
result={'status':'PASS' if not bad and not hits else 'FAIL','files_and_members_scanned':count,'uncompressed_bytes_scanned':total,'private_path_or_exact_copy_matches':sorted(set(bad)),'known_secret_or_individual_hash_matches':sorted(set(hits)),'actual_secret_classes':classes,'secret_values_or_individual_hashes_emitted':False,'public_source_zip_sha256':sha(product/'aevora-gen15-public-source.zip'),'image_tar_sha256':sha(image),'authority':'ACTUAL_SOURCE_AND_ARCHIVE_MEMBERS_AND_DOCKER_LAYERS','at':now()}
write(E/'05_product/PUBLIC_RELEASE_SCAN.json',result);print(json.dumps(result));raise SystemExit(0 if result['status']=='PASS' else 1)
