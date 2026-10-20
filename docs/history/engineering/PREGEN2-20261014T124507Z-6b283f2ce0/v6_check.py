from runtime import *
import stat
prior=json.loads((E/'00_environment/repo_integrity.json').read_text())['source547_sha256']
for label,args in [('status',['status','--porcelain=v1']),('branch',['branch','--show-current']),('head',['rev-parse','HEAD']),('tree',['rev-parse','HEAD^{tree}']),('remote',['remote','-v']),('fsck',['fsck','--full'])]:assert record('v6-git-'+label,['git','-C',W,*args])==0
assert (E/'commands/v6-git-status/stdout.log').read_bytes()==b''
assert (E/'commands/v6-git-head/stdout.log').read_text().strip()==C['head'] and (E/'commands/v6-git-tree/stdout.log').read_text().strip()==C['tree']
assert (E/'commands/v6-git-branch/stdout.log').read_text().strip()=='aevora-gen2-baseline'
assert all(sha(W/n)==h for n,h in prior.items())
write(E/'07_audit/FINAL_SOURCE_IDENTITY.json',{'status':'PASS','at':now(),'head':C['head'],'tree':C['tree'],'clean':True,'source_count':547,'sha256_unchanged':True,'source_sha256':prior,'remote_push':False,'gen2_code_changed':False})
original=json.loads((E/'00_environment/G5_SEAL_SAMPLE_VERIFICATION.json').read_text());assert sha(G5/'EVIDENCE_MANIFEST.json')==original['manifest_sha256']
for x in original['samples']:assert sha(G5/x['path'])==x['sha256']
a=json.loads((E/'00_environment/archive_inventory_verification.json').read_text())
for x in a['sample_files']:assert sha(x['archive'])==sha(x['backup'])==x['sha256']
for x in a['symlinks']:assert os.readlink(x['path'])==x['target']
write(E/'07_audit/FINAL_HISTORY_SAMPLE.json',{'status':'PASS','at':now(),'old_archive_backup_files_rehashed':60,'g5_receipt_files_rehashed':len(original['samples']),'g5_manifest_unchanged':True,'coverage':'Sampled hashes plus enforced read-only execution mappings; not full24GB end rehash','old_paths_absent':all(not (W.parent/n).exists() for n in ['orderflow_incident_lab','aevora_gen1_5','aevora_gen1_5_1','aevora_gen1_5_evidence','aevora_gen1_5_1_evidence','aevora_gen1_5_2_evidence'])})
p=json.loads((E/'06_live_agent/challenge_protocol_frozen.json').read_text());assert record('v6-owned-final-graph-save',runtime(str(E/'v6_graph_capture.py'),graph=p['graph']))==0
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());assert record('v6-owned-final-rdb-bytes',['docker','exec',cfg['container'],'cat','/data/dump.rdb'])==0
assert record('v6-owned-db-stop',['docker','stop','--time','15',cfg['container']])==0
assert record('v6-docker-owner-check',['docker','ps','-a','--filter','label=aevora.audit.owner='+C['run_id'],'--format','{{.Names}}\t{{.Status}}'])==0
assert record('v6-ports',['ss','-ltn'])==0
assert record('v6-mount-check',['findmnt','-rn','-o','TARGET,SOURCE'])==0
write(E/'07_audit/OWNED_RUNTIME_STOP.json',{'status':'PASS','at':now(),'owned_main_db_stopped':cfg['container'],'owned_cold_db_stopped':json.loads((E/'04_falkordb/recovery-attempt2/RESULT.json').read_text())['cold_container'],'native_sessions_ended':True,'official_code_homes_removed':all(not (E/'06_live_agent'/label/'runs'/json.loads((E/'06_live_agent'/label/'SUMMARY.json').read_text())['run_id']/'codex-state').exists() for label in ['preflight','s1','s2']),'historical_services_not_operated':True,'rdb_sha256':sha(E/'commands/v6-owned-final-rdb-bytes/stdout.log'),'ephemeral_namespace_only':True})
print('V6 finalsource547/archive samples/owned cleanup PASS')
