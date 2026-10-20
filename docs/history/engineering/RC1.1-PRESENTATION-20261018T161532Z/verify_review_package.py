#!/usr/bin/env python3
import argparse,hashlib,json,zipfile
from pathlib import Path,PurePosixPath

def sha(f):
    h=hashlib.sha256()
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument('zip_path',type=Path)
    a.add_argument('--sha256')
    args=a.parse_args()
    with args.zip_path.open('rb') as f: outer=sha(f)
    if args.sha256 and outer!=args.sha256.lower():raise ValueError('Outer ZIP hash mismatch')
    p='Aevora_RC11_Review/'
    with zipfile.ZipFile(args.zip_path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate member')
        for n in names:
            q=PurePosixPath(n)
            if not n.startswith(p) or q.is_absolute() or '..' in q.parts or '\\' in n:raise ValueError('Unsafe member path')
        raw=z.read(p+'PACKAGE_MANIFEST.json')
        m=json.loads(raw)
        expected={p+e['path'] for e in m['files']}|{p+'PACKAGE_MANIFEST.json',p+'SHA256SUMS.txt'}
        if set(names)!=expected:raise ValueError('Member set mismatch')
        sums=[]
        for e in m['files']:
            n=p+e['path']
            if z.getinfo(n).file_size!=e['bytes']:raise ValueError('Size mismatch: '+n)
            with z.open(n) as f:actual=sha(f)
            if actual!=e['sha256']:raise ValueError('SHA256 mismatch: '+n)
            sums.append(e['sha256']+'  '+e['path'])
        sums.append(hashlib.sha256(raw).hexdigest()+'  PACKAGE_MANIFEST.json')
        if z.read(p+'SHA256SUMS.txt').decode()!='\n'.join(sums)+'\n':raise ValueError('Checksum list mismatch')
    print(json.dumps({'status':'PASS','files':len(names),'all_member_hashes':'PASS','sha256':outer},sort_keys=True))

if __name__=='__main__':main()
