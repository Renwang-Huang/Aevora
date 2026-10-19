from audit import *
from runtime import runtime
cfg=json.loads((E/'RUNTIME_CONFIG.json').read_text());name=json.loads((E/'04_live/INITIAL_GRAPH.json').read_text())['graph']
assert json.loads((E/'commands/g5-full-post-feedback-negative-controls-attempt2/receipt.json').read_text())['exit_code']==0
owner=__import__('subprocess').check_output(['docker','inspect','--format','{{ index .Config.Labels "aevora.audit.owner" }}',cfg['container']],text=True).strip();assert owner==E.name
assert record('g5-real-db-before-save',runtime(E/'db_probe.py','before',graph=name))==0
assert record('g5-owned-db-real-stop',['docker','stop','--time','30',cfg['container']])==0
assert record('g5-stopped-container-state',['docker','inspect','--format','{{json .State}}',cfg['container']])==0
try:
 assert record('g5-real-db-offline-mcp',runtime(E/'db_probe.py','offline',graph=name))==0
 assert record('g5-real-db-offline-console',runtime(E/'offline_console_probe.py',graph=name))==0
finally:
 assert record('g5-owned-db-real-start',['docker','start',cfg['container']])==0
assert record('g5-real-db-after-reload',runtime(E/'db_probe.py','after',graph=name))==0
assert record('g5-real-db-reload-logs',['docker','logs',cfg['container']])==0
assert record('g5-post-restart-full-mcp-health',runtime(E/'full_graph_health.py','after_restart',graph=name))==0
write(E/'05_graph/COLD_RECOVERY_RESULT.json',{'status':'PASS','at':now(),'real_container_stop_start':True,'same_owned_graph':name,'original_live_graph_exact_restore':json.loads((E/'05_graph/db_outage/RESULT.json').read_text())['full_live_graph_exact_restoration'],'mcp_outage_explicit':True,'console_live_outage_503_no_fallback':True,'complete_public_evidence_after_reconnect':True,'aof139':'NOT_FIXED_NOT_RETESTED','power_loss_or_unsaved_tail':'UNVERIFIED','model_requests':0})
print('G5_REAL_COLD_RDB_RECOVERY_PASS')
