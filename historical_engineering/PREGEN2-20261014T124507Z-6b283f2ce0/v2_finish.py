from runtime import *
import csv
assert record('v2-three-physical-boundaries',runtime('scripts/aevora_h2_security.py','isolation',str(E/'03_benchmark/negative_transport_trials/physical'),native=True))==0
cli=json.loads((E/'03_benchmark/cli/summary.json').read_text());old=json.loads((G5/'g5/cli/summary.json').read_text())
assert len(cli['commands'])==len(old['commands'])==15
contract=[];oracles=[]
for x,y in zip(cli['commands'],old['commands']):
 assert x['label']==y['label'] and x['expected_exit_code']==y['expected_exit_code'] and x['expected_status']==y['expected_status'] and x['checks_pass']
 contract.append({'case_id':x['label'],'expected_semantics':x['expected_status'],'actual_status':x['status'],'exit_code':x['exit_code'],'expected_exit_code':x['expected_exit_code'],'fresh_run_id':x.get('run_id'),'evidence_path':str(E/'03_benchmark/cli')})
 if (x.get('test_counts') or {}).get('collected'):
  oracles.append({'case':x['label'],'run_id':x['run_id'],'status':x['status'],**x['test_counts']})
with (E/'03_benchmark/cli_contract_15.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(contract[0]));w.writeheader();w.writerows(contract)
dv=json.loads((E/'03_benchmark/dv02/SUMMARY.json').read_text());write(E/'03_benchmark/ORACLE_MATRIX.json',{'cli_oracles':oracles,'dv02':dv,'prior_case_identity_exact':True})
reg=json.loads((E/'02_regression/regression_summary.json').read_text())
write(E/'03_benchmark/V2_RESULT.json',{'status':'PASS' if reg['status']=='PASS' and cli['status']=='PASS' and dv['status']=='PASS' else 'FAIL','at':now(),'regression':reg['status'],'cli_cases':15,'native_physical_isolation':'PASS','scope':'original1836 +15 original CLI cases +D-v02 positive/negative; fresh actual receipts; expected negative outcomes retained'})
print('V2_RESULT',reg['status'],cli['status'],dv['status'])
