from audit import *
rows=[]
expected={'g23-predicate-red':'EXPECTED_RED_REPRODUCTION'}
for f in sorted((E/'commands').glob('*/receipt.json')):
 d=json.loads(f.read_text())
 if d['exit']:
  rows.append({'command':f.parent.name,'exit':d['exit'],'receipt_sha256':sha(f),'receipt':str(f.relative_to(E)),'classification':expected.get(f.parent.name,'ORIGINAL_NONZERO_RETAINED'),'stdout_sha256':d['stdout_sha256'],'stderr_sha256':d['stderr_sha256']})
native=[]
for f in sorted((E/'04_live').glob('*/ORIGINAL_RUN_SUMMARY.json')):
 d=json.loads(f.read_text());native.append({'attempt':f.parent.name,'summary':str(f.relative_to(E)),'sha256':sha(f),'run_id':d['run_id'],'runtime':d['runtime_result'],'evaluation':d['evaluation_result'],'integration':d['integration_result'],'original_overall':d['overall_status'],'no_upgrades_from_diagnostics':True})
write(E/'G23_FAILURE_LEDGER_CURRENT.json',{'at':now(),'classification':'INTERMEDIATE_APPEND_ONLY_ORIGINALS_RETAINED','commands':rows,'original_native_runs':native,'engine_failure':{'exit':139,'signal':11,'oom_killed':False,'root_cause':'UNVERIFIED','old_container_retained':True,'last_save_backup':'05_security/db-crash-139'},'all_expected_red_and_actual_failures':'separate from final acceptance'})
print('nonzero commands',len(rows),'closed native originals',len(native))
