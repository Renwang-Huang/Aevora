from audit import *
import stat
O=Path(C['old_full']);manifest=O/'private_full/FULL_MANIFEST.json';assert sha(manifest)=='c02d55b95e074a6b301c5788604e52918bf5e92beac41fa886bff6f20d7e6ab7';m=json.loads(manifest.read_text());bad=[]
for n,v in m['files'].items():
 p=O/n
 try:
  s=p.lstat()
  if not stat.S_ISREG(s.st_mode) or sha(p)!=v['sha256'] or s.st_size!=v['bytes'] or oct(s.st_mode&0o777)!=v['mode'] or s.st_mtime_ns!=v['mtime_ns']:bad.append(n)
 except OSError:bad.append(n)
linkbad=[]
for v in m['links']:
 n=v['path']
 p=O/n
 try:
  expected=v['target'] if isinstance(v,dict) else v
  if not p.is_symlink() or os.readlink(p)!=expected:linkbad.append(n)
 except OSError:linkbad.append(n)
write(E/'00_baseline/HISTORICAL_FULL_INTEGRITY_CHECK.json',{'at':now(),'status':'PASS' if not bad and not linkbad else 'FAIL','manifest_sha256':sha(manifest),'file_count':len(m['files']),'checked_content_bytes_mode_mtime':True,'symlink_count':len(m['links']),'file_mismatches':bad,'link_mismatches':linkbad,'scope':'ENTIRE SEALED V5C FULL; other historical corpora mounted read-only during inherited tests, not a fresh global hash audit'})
print('HISTORICAL_FULL',len(m['files']),len(m['links']),'mismatches',len(bad),len(linkbad));assert not bad and not linkbad
