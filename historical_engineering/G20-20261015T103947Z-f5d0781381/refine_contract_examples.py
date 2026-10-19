from audit import *
import json,copy
K=P/'docs/gen2/g20/contracts'
# Strict identifier syntax matches the existing source's 1..240 allowlisted ASCII contract.
pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$'
def walk(v):
 if isinstance(v,dict):
  if v.get('type')=='string' and v.get('minLength')==1 and v.get('maxLength')==240:v['pattern']=pattern
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
for p in K.glob('*.schema.json'):
 d=json.loads(p.read_text());walk(d);p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
p=K/'examples.json';d=json.loads(p.read_text());pos=d['positive'];neg=d['negative'];src=pos[0]['value']['source_refs'][0]
event={'contract_version':'aevora.event/2.0.0-rc1','event_id':'event:synthetic','kind':'SessionStarted','tenant_id':'tenant:synthetic','run_id':'run:synthetic','session_id':None,'native_thread_id':None,'parent_thread_id':None,'identity_availability':'UNAVAILABLE','identity_reason':'Synthetic example, no Runtime invoked.','authority_class':'SYNTHETIC_PROBE','observed_at':'2026-10-15T11:00:00Z','official_at':None,'source_ref':src,'payload_sha256':'a'*64,'payload':{'synthetic':True}}
pos.extend([
{'schema':'event.schema.json','name':'synthetic-event-not-a-runtime','value':event},
{'schema':'tool_result.schema.json','name':'empty-is-not-pass','value':{'status':'EMPTY','contract_version':'aevora.mcp/2.0.0-rc1','query_id':'query:synthetic','semantic_epoch':0,'authz_epoch':0,'candidate_count':0,'candidates':[],'has_more':False,'next_cursor':None,'truncated':False}},
{'schema':'tool_result.schema.json','name':'explicit-db-unavailable','value':{'status':'ERROR','code':'GRAPH_UNAVAILABLE','retryable':True,'message':'Graph unavailable; no fallback.','contract_version':'aevora.mcp/2.0.0-rc1'}},
{'schema':'host_review.schema.json','name':'reject-without-invented-source','value':{'contract_version':'aevora.host.review/2.0.0-rc1','candidate_id':'candidate:synthetic','expected_head_sha256':'a'*64,'expected_semantic_epoch':1,'idempotency_key':'reject-1','action':'REJECTED','reason':'Independent evidence absent.'}}])
for name,path in [('event-absolute-path','/private/file.jsonl'),('event-traversal','../../hidden.jsonl')]:
 e=copy.deepcopy(event);e['source_ref']['file']=path;neg.append({'schema':'event.schema.json','name':name,'value':e,'expected':'REJECT_SCHEMA'})
e=copy.deepcopy(pos[0]['value']);e['authority_ref']='bad identifier with space';neg.append({'schema':'fact.schema.json','name':'invalid-stable-id','value':e,'expected':'REJECT_SCHEMA'})
e=copy.deepcopy(pos[2]['value']);e['arguments']['cursor']='X'*257;neg.append({'schema':'mcp_v2.schema.json','name':'oversized-cursor','value':e,'expected':'REJECT_SCHEMA'})
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
p=P/'docs/gen2/g20/MCP_COMPATIBILITY_AND_VERSIONING.md';s=p.read_text();s+='\n## 时间格式的显式断言\n\nJSON Schema的format可能仅为annotation，不能假设安装jsonschema就一定校验date-time。本次设计检查真实发现该依赖缺口；生产必须复用现有parse_timestamp并规范为UTC、明确验证timezone/日历，不依赖可缺少的RFC3339可选包。G20检查使用Python标准datetime显式检查；原始失败JUnit保留。schema是结构合同，不是authority或payloadSHA存在性的证明。\n';p.write_text(s)
print('STRICT_IDENTIFIER_AND_PROTOCOL_EXAMPLES_REFINED')
