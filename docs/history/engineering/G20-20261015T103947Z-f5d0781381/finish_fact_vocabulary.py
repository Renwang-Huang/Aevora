from audit import *
import json
D=P/'docs/gen2/g20';K=D/'contracts';p=K/'fact.schema.json';d=json.loads(p.read_text())
add={'task.worker_count_known':{'type':'boolean'},'task.observed_failure_mode':{'type':'string','minLength':1,'maxLength':512},'task.shared_object_scope':{'type':'string','minLength':1,'maxLength':512},'task.sqlite_journal_mode':{'type':'string','minLength':1,'maxLength':512}}
registry=d['$defs']['RegisteredFactValueTypes']['properties'];registry.update(add)
d['properties']['key']['enum']=list(registry)
for k,t in add.items():d['allOf'].append({'if':{'properties':{'key':{'const':k},'availability':{'const':'KNOWN'}}},'then':{'properties':{'value':t}}})
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
for name in ['propose_experience.arguments.schema.json','mcp_v2.schema.json']:
 p=K/name;x=json.loads(p.read_text());body=x['properties']['proposal'] if name.startswith('propose') else x['$defs']['propose_experience']['properties']['proposal']
 for f in ['necessary_conditions','inapplicable_conditions','scope']:
  c=body['properties'][f]
  for k,t in add.items():
   if k not in c['propertyNames']['enum']:c['propertyNames']['enum'].append(k)
   c['properties'][k]={'type':'array','minItems':1,'maxItems':32,'items':t}
 body['properties']['unknown_fields']['items']['enum']=list(registry)
 p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
p=D/'MCP_COMPATIBILITY_AND_VERSIONING.md';s=p.read_text().replace('其余已注册事实为≤512字符的公开语义label','task.worker_count_known为严格boolean，其余已注册事实为≤512字符的公开语义label');s+='\n旧Host17项公开facts的词汇全部有显式v2映射：除authority_validation按明确phase保留为artifact_before/after，其他均task.*；新增evaluation.test_suite_fingerprint只作独立结果来源。旧flat记录不会自动重标，导入adapter须保留legacy语义或重新取得独立phase事实。\n';p.write_text(s)
p=D/'test_design_contracts.py';p.write_text(p.read_text()+'''\ndef test_entire_legacy_host_fact_vocabulary_has_explicit_v2_mapping():\n legacy={'concurrency_scope','worker_count','worker_count_known','shared_state_kind','synchronization_scope','transaction_guarantees','observed_failure_mode','shared_object_scope','sqlite_journal_mode','operation_semantics','authority_model','clock_domain','failure_domain','contract_version','lease_expiry_semantics','authority_validation','supported_operation_set'}\n keys=set(load(K/'fact.schema.json')['properties']['key']['enum'])\n assert {'task.'+k for k in legacy-{'authority_validation'}}<=keys\n assert {'artifact_before.authority_validation','artifact_after.authority_validation'}<=keys\n assert 'task.authority_validation' not in keys\n''')
print('ALL17_LEGACY_FACTS_EXPLICIT_V2_MAPPING_COMPLETE')
