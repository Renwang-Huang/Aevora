"""Final read-only source/history verification, owned resource quiescence."""
from audit import *
import stat,hashlib
P=E/'owned_runtime/source';initial=json.loads((E/'00_environment/BASELINE_IDENTITY.json').read_text());freeze=json.loads((E/'source/SOURCE_TRUST_MANIFEST.json').read_text())
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True).strip()
bad=[n for n,h in initial['source547_sha256'].items() if sha(W/n)!=h]
patchbad=[n for n,h in freeze['files'].items() if sha(P/n.removeprefix('frozen_source_snapshot/'))!=h]
assert not bad and not patchbad and not git(W,'status','--porcelain=v1') and not git(P,'status','--porcelain=v1')
assert git(W,'rev-parse','HEAD')==initial['head'] and git(W,'rev-parse','HEAD^{tree}')==initial['tree']
write(E/'07_audit/FINAL_SOURCE_IDENTITY.json',{'status':'PASS','frozen_main_head':git(W,'rev-parse','HEAD'),'frozen_main_tree':git(W,'rev-parse','HEAD^{tree}'),'main_clean':True,'baseline_paths_verified':len(initial['source547_sha256']),'main_deltas':bad,'closure_head':git(P,'rev-parse','HEAD'),'closure_tree':git(P,'rev-parse','HEAD^{tree}'),'closure_clean':True,'frozen_patch_paths_verified':len(freeze['files']),'closure_deltas':patchbad,'at':now()})
old=Path('/home/PRIVATE_MAINTAINER/data_storage/aevora_validation_runs/PREGEN2-20261014T124507Z-6b283f2ce0');mp=old/'private_full/FULL_MANIFEST.json';j=json.loads(mp.read_text());mismatches=[];total=0
for n,d in j['files'].items():
 p=old/n
 if not p.is_file() or p.is_symlink() or sha(p)!=d['sha256'] or p.stat().st_size!=d['bytes']:mismatches.append(n)
 else:total+=d['bytes']
links=j.get('links',{});linkbad=[]
items=links.items() if isinstance(links,dict) else [(v['path'],v) for v in links]
for n,d in items:
 p=old/n;target=d.get('target',d.get('link_target')) if isinstance(d,dict) else d
 if not p.is_symlink() or (target is not None and os.readlink(p)!=target):linkbad.append(n)
assert not mismatches and not linkbad
assert sha(mp)==initial['old_full_manifest_json_sha256'] and sha(old/'private_full/FULL_MANIFEST.sha256')==initial['old_full_manifest_sha256']
write(E/'07_audit/HISTORICAL_FULL_FINAL_REHASH.json',{'status':'PASS','scope':'Complete old PreGen2 Full byte and symlink read-only recheck; not an audit rerun of all six historical archives','files':len(j['files']),'bytes':total,'links':len(links),'file_mismatches':mismatches,'link_mismatches':linkbad,'manifest_json_sha256':sha(mp),'manifest_checksum_sha256':sha(old/'private_full/FULL_MANIFEST.sha256'),'at':now()})
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());container=cfg['container'];inspect=json.loads(subprocess.check_output(['docker','inspect',container]))[0];assert inspect['Config']['Labels']['aevora.audit.owner']==E.name
assert record('c5-owned-db-final-normal-stop',['docker','stop','--time','20',container])==0
inspect=json.loads(subprocess.check_output(['docker','inspect',container]))[0]
states=[]
for label in ['01_c1_repairs/native_preflight','02_live_s1','04_live_s2']:
 run=next((E/label/'runs').iterdir());m=json.loads((run/'runtime_metadata.json').read_text());manifest=json.loads((run/'run_evidence_manifest.json').read_text())
 assert all(sha(run/n)==h for n,h in manifest['files'].items())
 cg=m['resource_cgroup'];assert cg['cleanup_complete'] and not Path(cg['path']).exists() and not (run/'codex-state').exists()
 states.append({'run_id':run.name,'native_exit':m['exit_code'],'run_seal_sha256':sha(run/'run_evidence_manifest.json'),'sealed_files_verified':len(manifest['files']),'cgroup_absent':True,'codex_state_removed':True})
write(E/'07_audit/OWNED_RESOURCE_CLOSURE.json',{'status':'PASS','container':container,'container_state':inspect['State']['Status'],'running':inspect['State']['Running'],'restart_policy':inspect['HostConfig']['RestartPolicy'],'active_port_released':not inspect['State']['Running'],'retained_forensic_resources':['Stopped owned container configuration','Owned DB RDB files and runtime snapshot; no active services','External project-specific password files remain0600, never in archive'],'native_runs':states,'historical_services_operated':False,'at':now()})
print('FINAL_INTEGRITY_PASS',len(initial['source547_sha256']),len(freeze['files']),len(j['files']),total)
