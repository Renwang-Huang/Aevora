from audit import *
import json
K=P/'docs/gen2/g20/contracts';D=K.parent
sha_s={'type':'string','pattern':'^[0-9a-f]{64}$'};ident={'type':'string','minLength':1,'maxLength':240,'pattern':r'^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$'};epoch={'type':'integer','minimum':0,'maximum':2**63-1}
def o(props,required=None):return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
def out(name,shape):
 shape={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://aevora.invalid/contracts/2.0.0-rc1/'+name,'$comment':'PROPOSED structural contract; only independently authorized Host may instantiate trusted records; schema alone grants no authority.',**shape}
 (K/name).write_text(json.dumps(shape,indent=2)+'\n')
current=json.loads((D/'contracts/graph_v2_catalog.json').read_text())
transitions={'PROPOSED':['EVIDENCE_PENDING','REJECTED'],'EVIDENCE_PENDING':['ADMITTED_BOUNDED','REJECTED'],'ADMITTED_BOUNDED':['PUBLISHING','WITHDRAWN'],'PUBLISHING':['PUBLISHED','WITHDRAWN'],'PUBLISHED':['WITHDRAWN','SUPERSEDED'],'REJECTED':[],'WITHDRAWN':[],'SUPERSEDED':[]}
(K/'lifecycle_transition_catalog.json').write_text(json.dumps({'version':'aevora.lifecycle/2.0.0-rc1','status':'PROPOSED','legacy_states_retained':True,'trust_of_PROPOSED':'PROPOSED_UNTRUSTED','transitions':transitions,'head_mutable':True,'events_immutable':True,'publication_activation':'SAME_QUERY_HEAD_EVENT_COMMITS_EPOCH_FENCE','same_request_key_same_semantic_body':'RETURN_ORIGINAL_EVENT_NOT_CURRENT_HEAD','same_request_key_different_body':'IMMUTABLE_CONFLICT','request_digest_excludes':['ephemeral_grant_expiry','transport_connection_id'],'request_digest_includes':['tenant','principal','candidate','action','expected_head','expected_epoch','source','scope','reason'],'expiry_still_checked_on_new_execution':True,'replay_does_not_reactivate_or_reauthorize':True},indent=2)+'\n')
out('lifecycle_event.schema.json',o({'contract_version':{'const':'aevora.lifecycle/2.0.0-rc1'},'id':ident,'tenant_id':ident,'candidate_id':ident,'from_state':{'enum':[None,*transitions]},'to_state':{'enum':list(transitions)},'sequence':epoch,'previous_event_id':{'anyOf':[ident,{'type':'null'}]},'request_sha256':sha_s,'body_sha256':sha_s,'authority_ref':ident,'created_at':{'type':'string','format':'date-time'},'semantic_epoch':epoch}))
out('independent_outcome.schema.json',o({'contract_version':{'const':'aevora.outcome/2.0.0-rc1'},'id':ident,'tenant_id':ident,'run_id':ident,'evaluator_run_id':ident,'verdict':{'enum':['PASS','FAIL','ERROR','TIMEOUT','NOT_IMPLEMENTED']},'submission_sha256':sha_s,'candidate_tree_sha256':sha_s,'source_manifest_sha256':sha_s,'evaluator_sha256':sha_s,'private_manifest_sha256':sha_s,'test_suite_sha256':sha_s,'junit_sha256':sha_s,'oracle_receipt_sha256':sha_s,'authority_ref':ident,'source_type':{'enum':['current_independent_evaluation','historical_authorized_import','controlled_independent_negative']},'attribution':{'const':'UNKNOWN'},'causal_benefit':{'const':'UNKNOWN'}}))
chunk=o({'id':ident,'index':{'type':'integer','minimum':0,'maximum':127},'sha256':sha_s})
manifest=o({'contract_version':{'const':'aevora.document-manifest/2.0.0-rc1'},'id':ident,'tenant_id':ident,'document_kind':{'enum':['QUERY_SNAPSHOT','PUBLICATION_RECORD_SET']},'document_sha256':sha_s,'document_utf8_bytes':{'type':'integer','minimum':1,'maximum':8388608},'encoding':{'enum':['INLINE_CANONICAL_JSON','UTF8_TEXT_CHUNKS']},'chunk_count':{'type':'integer','minimum':0,'maximum':128},'chunks':{'type':'array','maxItems':128,'uniqueItems':True,'items':chunk},'inline_document':{'type':['object','null']}},None)
manifest['allOf']=[{'if':{'properties':{'encoding':{'const':'INLINE_CANONICAL_JSON'}}},'then':{'properties':{'chunk_count':{'const':0},'chunks':{'maxItems':0},'inline_document':{'type':'object'}}},'else':{'properties':{'chunk_count':{'minimum':1},'chunks':{'minItems':1},'inline_document':{'type':'null'}}}}]
out('document_manifest.schema.json',manifest)
current['new_relationships'].append({'source':'PublicationManifest','type':'HAS_CHUNK','target':'SnapshotChunk','authority':'STORAGE_FACT'})
(K/'graph_v2_catalog.json').write_text(json.dumps(current,indent=2)+'\n')
for name in ['03_EXPERIENCE_GRAPH_V2_SCHEMA.md','GRAPH_CYPHER_CONTRACTS.md','ARCHITECTURE_DECISIONS.md']:
 p=D/name;s=p.read_text()
 if name.startswith('03_'):
  s+='\nPublicationManifest的大型record-set清单也使用同一bounded文档manifest和SnapshotChunk/HAS_CHUNK存储（不新建blob数据库）。root只存expectedepoch、candidate/source/outcome摘要和完整listing的documentSHA/orderedchunkrefs；实际读取并重组listing后核对全关系。不是只信一个complete=true。QuerySnapshot和PublicationManifest最多128chunks、每块64KiB UTF8、整体8MiB；任何缺块/跨tenant/哈希错都明确失败。typed schemas包含document/lifecycle/independent outcome，但结构符合不赋予Host权威。\n'
 elif name.startswith('GRAPH_'):
  s=s.replace('最坏查询数≤2+5*256','最坏查询数≤2+7*256（包括每manifest一次有界批量chunk读取）')
  s+='\nSnapshot和Publication record-set的chunk读取使用固定`MATCH (m)-[h:HAS_CHUNK]->(c:SnapshotChunk) WHERE m.tenant_id=$tenant AND c.tenant_id=$tenant RETURN h.id,c.id,c.chunk_index,c.payload_json,c.payload_sha256 ORDER BY c.chunk_index LIMIT 129`，Host绑定manifest id并验证实际typed关联、顺序与全SHA；模板在此为PROPOSED/NOT_EXECUTED。不得对每chunk额外无界循环单查询，计入20MiB/总query/wall预算。Q03读取受限直接SUPERSEDES边后以有界DAG校验深度，避免枚举指数数量的所有变长path。\n'
 else:s+='\n### ADR-05 补充：Publication manifest清单同样有record预算\n\n512条证据路径的完整节点/关系声明可能超过256KiB；不允许仅快照分块而publication清单仍无界。统一沿HAS_CHUNK将大型record-set存为有界SnapshotChunk，root记录完整document hash/有序chunkrefs；Q07只在Host已独立重组校验完后激活root。与Q00 epoch重读、必需边集合比对共同防止部分清单变成完整推荐。生产完整实现与故障注入属于G2-1/2，G20未执行。\n'
 p.write_text(s)
print('LIFECYCLE_OUTCOME_AND_BOUNDED_MANIFEST_CONTRACTS_COMPLETE')
