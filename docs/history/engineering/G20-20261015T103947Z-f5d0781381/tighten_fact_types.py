from audit import *
import json,copy
D=P/'docs/gen2/g20';K=D/'contracts'
p=K/'fact.schema.json';d=json.loads(p.read_text());keys=d['properties']['key']['enum']
value_types={k:({'type':'integer','minimum':1,'maximum':4096} if k=='task.worker_count' else {'type':'string','minLength':1,'maxLength':512}) for k in keys}
for k,v in value_types.items():d['allOf'].append({'if':{'properties':{'key':{'const':k},'availability':{'const':'KNOWN'}}},'then':{'properties':{'value':v}}})
d['$defs']={'RegisteredFactValueTypes':{'description':'Host registration registry; values only known with independent source. Strings are public labels, not parsable repair instructions.','type':'object','properties':value_types,'additionalProperties':False}}
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
for name in ['propose_experience.arguments.schema.json','mcp_v2.schema.json']:
 p=K/name;x=json.loads(p.read_text());body=x['properties']['proposal'] if name.startswith('propose') else x['$defs']['propose_experience']['properties']['proposal']
 for f in ['necessary_conditions','inapplicable_conditions','scope']:
  c=body['properties'][f];allowed=c['propertyNames']['enum'];c['properties']={k:{'type':'array','minItems':1,'maxItems':32,'items':value_types[k]} for k in allowed};c['additionalProperties']=False
 p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
p=D/'MCP_COMPATIBILITY_AND_VERSIONING.md';p.write_text(p.read_text()+'\n已注册fact value类型冻结在fact.schema.json的RegisteredFactValueTypes：task.worker_count为1..4096的严格integer（不是bool），其余已注册事实为≤512字符的公开语义label。supported_operation_set是声明的operation-group label，不把任意文本当集合解析。KNOWN的phase/key/value类型和独立来源必须同时匹配。v2提案scope/必要/排除条件的allowed-values逐key使用同一类型，不能以bool代count或将artifact_after塞进前提。扩展registry是版本化合同变更。\n')
p=D/'test_design_contracts.py';s=p.read_text()+'''\n@pytest.mark.parametrize('bad',[True,'4',0,4097])\ndef test_registered_worker_count_type_cannot_be_coerced(bad):\n d=copy.deepcopy(EX['positive'][0]['value']);d.update(key='task.worker_count',value=bad)\n assert list(Draft202012Validator(load(K/'fact.schema.json')).iter_errors(d))\n''';p.write_text(s)
print('FACT_REGISTRY_TYPES_FROZEN_NO_PRODUCT_CHANGE')
