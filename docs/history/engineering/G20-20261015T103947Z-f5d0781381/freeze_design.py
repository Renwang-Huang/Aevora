from audit import *
import json,csv,xml.etree.ElementTree as ET
D=P/'docs/gen2/g20'
cs=list(ET.parse(E/'checks/final-acceptance/JUNIT.xml').getroot().iter('testcase'));assert cs and all(not list(c) for c in cs)
assert len({(c.get('classname'),c.get('name')) for c in cs})==len(cs)
probe=json.loads((E/'probes/attempt2/RESULT.json').read_text());assert probe['status']=='PASS_SYNTHETIC_QUERY_AND_CONSTRAINT_SHAPES_ONLY'
files={str(p.relative_to(D)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(D.rglob('*')) if p.is_file() and p.name!='CONTRACT_FREEZE_INDEX.json'}
expected=set(r['path_or_module'].removeprefix('docs/gen2/g20/') for r in csv.DictReader((D/'HACKATHON_CONTRIBUTION_MATRIX.csv').open()) if r['classification']=='G20_NEW_DESIGN_CONTRACT_ASSET')
assert expected==set(files)|{'CONTRACT_FREEZE_INDEX.json'},(expected-set(files),set(files)-expected)
write(D/'CONTRACT_FREEZE_INDEX.json',{'schema':'aevora.g20.freeze/1','created_at':now(),'contract_version':'aevora.gen2.contract/2.0.0-rc1','graph_version':'aevora.graph/2.0.0-rc1','mcp_version':'aevora.mcp/2.0.0-rc1','status':'FROZEN_CANDIDATE_PENDING_INDEPENDENT_REVIEW','source_base':C['base_head'],'source_base_tree':C['base_tree'],'new_design_files':len(files)+1,'files':files,'self_boundary':['CONTRACT_FREEZE_INDEX.json'],'current_design_checks':{'passed':len(cs),'failed':0,'errors':0,'skipped':0,'junit_sha256':sha(E/'checks/final-acceptance/JUNIT.xml'),'classification':'SCHEMA_AND_ARTIFACT_CONTRACT_TESTS_ONLY_NOT_PRODUCT_OR_INHERITED_REGRESSION'},'synthetic_probe_status':probe['status'],'production_gen2_implementation':'NOT_IMPLEMENTED','new_native_multi_agent':'NOT_RUN','inherited1897_rerun':'NOT_RUN','next_gate':'G2-1_NOT_AUTHORIZED_UNTIL_INDEPENDENT_REVIEW'})
write(E/'source_audit/CONTRACT_FREEZE_RECEIPT.json',{'status':'PASS_LOCAL_DESIGN_FREEZE','at':now(),'freeze_index_sha256':sha(D/'CONTRACT_FREEZE_INDEX.json'),'files':len(files)+1,'design_tests':len(cs),'worktree':str(P),'live_model_requests':0,'source_production_changes':0})
print('FROZEN_DESIGN_FILES',len(files)+1,'DESIGN_TESTS',len(cs))
