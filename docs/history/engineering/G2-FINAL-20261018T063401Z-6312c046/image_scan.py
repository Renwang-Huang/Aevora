from audit import *
import tarfile
out=E/'final/image-audit';out.mkdir(exist_ok=False);archive=out/'owned-public-image.tar';image='aevora-gen2:6312c046-safe-rc1'
assert record('safe-image-save',['docker','image','save','--output',archive,image])==0
secrets=private_values();matches=[];forbidden=[];files=0;total=0;max_tail=max(map(len,secrets),default=1)
with tarfile.open(archive) as outer:
 manifest=json.load(outer.extractfile('manifest.json'))[0]
 config=json.load(outer.extractfile(manifest['Config']))
 serialized=json.dumps(config).encode();assert not any(s in serialized for s in secrets)
 for layer_name in manifest['Layers']:
  with tarfile.open(fileobj=outer.extractfile(layer_name),mode='r|*') as layer:
   for item in layer:
    name=item.name.removeprefix('./')
    if name.startswith(('opt/aevora/evaluator/','opt/aevora/benchmark/','opt/aevora/aevora_maintainer/','root/.codex/')) or name.endswith(('falkordb.password','gateway.key','auth.json')):forbidden.append(name)
    if not item.isfile():continue
    files+=1;total+=item.size;f=layer.extractfile(item);tail=b'';bad=False
    while True:
     b=f.read(1024*1024)
     if not b:break
     joined=tail+b
     if any(s in joined for s in secrets):bad=True
     tail=joined[-max_tail:]
    if bad:matches.append(name)
status='PASS' if not matches and not forbidden else 'FAIL'
write(out/'IMAGE_SCAN.json',dict(status=status,image=image,image_archive_sha256=sha(archive),image_archive_bytes=archive.stat().st_size,layers=len(manifest['Layers']),regular_files_inspected=files,uncompressed_bytes_inspected=total,known_credential_matches=matches,private_payload_path_matches=forbidden,config_environment=[s.split('=',1)[0] for s in config['config'].get('Env',[])],scope='All regular file bytes of every owned image layer and image configuration checked for known scoped credential values. No external model request. Not a general vulnerability scan.'))
print(status,files,total);raise SystemExit(0 if status=='PASS' else 1)
