from audit import *
import gzip,random,stat
manifest=json.loads((G5/'EVIDENCE_MANIFEST.json').read_text())
print('G5 manifest keys',list(manifest))
prior_samples=json.loads((G5/'restore/RANDOM_SAMPLE.json').read_text())['payloads']
roots=json.loads((G5/'CONFIG.json').read_text())
rows=[]
for r in prior_samples:
 b=Path(r['source_backup_path']);n=next(x for x in roots['sources'] if '/'+Path(x).name+'/' in str(b));rel=str(b).split('/'+Path(n).name+'/',1)[1];a=T/Path(n).name/rel
 assert a.is_file() and not a.is_symlink() and sha(a)==r['sha256'] and sha(b)==r['sha256']
 rows.append({'archive':str(a),'backup':str(b),'bytes':a.stat().st_size,'sha256':r['sha256'],'independent_inode':(a.stat().st_dev,a.stat().st_ino)!=(b.stat().st_dev,b.stat().st_ino),'status':'PASS'})
links=[]
for f in (G5/'manifests').glob('*.gz'):
 rootname='aevora_gen1_5_2_evidence' if f.name=='extra-source.jsonl.gz' else f.name.removesuffix('-source.jsonl.gz')
 chosen=[];count=0
 with gzip.open(f,'rt') as inp:
  for l in inp:
   d=json.loads(l);count+=1
   if d.get('kind')=='LINK' and len(chosen)<3:chosen.append(d)
 # Record manifest definition even when its symlink key differs; no guessed success.
 for d in chosen:
  rel=d.get('path');p=T/rootname/rel
  target=d.get('link',d.get('target',d.get('text')))
  actual=os.readlink(p);assert target is not None and actual==target
  links.append({'path':str(p),'target':actual,'status':'PASS'})
 print(f.name,'manifest_nodes',count,'row keys',list(d))
write(E/'00_environment/archive_inventory_verification.json',{'at':now(),'status':'PASS','coverage':'60 predetermined G5 restore sample files: fresh SHA of archive and independent backup copies; root existence; archive manifest full reads only, NOT full24GB SHA','sample_files':rows,'symlinks':links,'all_six_exist':all((T/Path(p).name).is_dir() for p in roots['sources']),'old_paths_absent':all(not Path(p).exists() for p in roots['sources']),'failure_domain':'SAME_FAILURE_DOMAIN; not independent disk disaster recovery','sealed_g5_manifest_sha':sha(G5/'EVIDENCE_MANIFEST.json')})
