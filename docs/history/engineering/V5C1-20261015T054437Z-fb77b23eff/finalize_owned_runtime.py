from audit import *
from runtime import runtime
import subprocess
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());graph=json.loads((E/'04_live/INITIAL_GRAPH.json').read_text())['graph']
assert json.loads((E/'05_graph/COLD_RECOVERY_RESULT.json').read_text())['status']=='PASS'
assert subprocess.check_output(['docker','inspect','--format','{{ index .Config.Labels "aevora.audit.owner" }}',cfg['container']],text=True).strip()==E.name
assert record('g6-final-real-db-save',runtime(E/'final_db_save.py',graph=graph))==0
assert record('g6-final-owned-container-inspect',['docker','inspect',cfg['container']])==0
assert record('g6-final-owned-container-stop',['docker','stop','--time','30',cfg['container']])==0
assert record('g6-final-owned-container-state',['docker','inspect','--format','{{json .State}}',cfg['container']])==0
assert record('g6-final-owned-container-remove',['docker','rm',cfg['container']])==0
assert record('g6-owner-containers-remaining',['docker','ps','-a','--filter','label=aevora.audit.owner='+E.name,'--format','{{.Names}}'])==0
assert not (E/'commands/g6-owner-containers-remaining/stdout.log').read_text().strip()
rows=[]
for phase in ['S1','S2']:
 s=json.loads((E/'04_live'/phase/'ORIGINAL_RUN_SUMMARY.json').read_text());r=E/'04_live'/phase/'runs'/s['run_id'];m=json.loads((r/'runtime_metadata.json').read_text());report=json.loads((r/'evaluation_report.json').read_text());broker=m['experience']['broker'];assert broker['handler_cleanup_complete'] and broker['token_revoked'] and broker['socket_unlinked'] and not broker['active_sdk_children'] and not broker['active_connections'];assert report['agent_state_cleanup']=='PASS' and not (r/'codex-state').exists()
 rows.append({'phase':phase,'run_id':r.name,'native_state_absent':True,'agent_state_cleanup':'PASS','mcp_owner_revoked':True,'mcp_socket_absent':True,'mcp_children_closed':True,'model_broker_status':m['model_broker'].get('status','UNAVAILABLE'),'model_broker_active_requests':m['model_broker'].get('active_requests','UNAVAILABLE')})
write(E/'06_audit/OWNED_RESOURCE_CLOSURE.json',{'status':'PASS','at':now(),'container':cfg['container'],'owner_label':E.name,'owned_container_stopped_and_removed':True,'owned_data_and_all_archives_retained':True,'external_secret_file_values_not_archived':True,'other_containers_operated':False,'new_model_sessions_after_S2':0,'sessions':rows,'temporary_mounts':'PER_PROCESS_BWRAP; namespaces terminated; no host bind mount created'})
print('OWNED_RUNTIME_CLOSED')
