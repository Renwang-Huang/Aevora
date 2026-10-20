from audit import *
import json,re,shutil
D=P/'docs/gen2/g20';Q=D/'cypher'
q6='''// PROPOSED / NOT_EXECUTED. Trusted service params only; UNIQUE(id) checked before write.
MATCH (s:TenantState {id:$state,tenant_id:$tenant})
WHERE s.epoch=$epoch AND s.authz_epoch=$authz_epoch
MERGE (n:Recommendation {id:$id,tenant_id:$tenant,record_version:$record_version,
 kind:'Recommendation',payload_json:$payload,payload_sha256:$sha,created_at:$created,
 source_type:'core_derived',authority_ref:$authority,visibility:'PUBLIC'})
ON CREATE SET n.run_id=$run,n.query_id=$query,n.experience_id=$experience,
 n.semantic_epoch=$epoch,n.core_verdict=$verdict,n.policy_version=$policy
RETURN n.payload_sha256,n.semantic_epoch
'''
(Q/'Q06_record_recommendation.cypher').write_text(q6)
q7='''// PROPOSED / NOT_EXECUTED full lifecycle activation; preparation validates every canonical record/edge.
MATCH (s:TenantState {id:$state,tenant_id:$tenant}),
      (c:Candidate {id:$candidate,tenant_id:$tenant})-[:HAS_LIFECYCLE]->(h:LifecycleHead {id:$head,tenant_id:$tenant}),
      (previous:CandidateEvent {id:$previous,tenant_id:$tenant}),
      (m:PublicationManifest {id:$manifest,tenant_id:$tenant})
WHERE s.epoch=$expected AND h.payload_sha256=$expected_head
  AND h.candidate_id=$candidate AND h.event_id=$previous AND previous.candidate_id=$candidate
  AND h.state='PUBLISHING' AND m.epoch=$next AND $next=$expected+1
  AND m.payload_sha256=$manifest_sha
CREATE (event:CandidateEvent {id:$event,tenant_id:$tenant,record_version:$record_version,
 kind:'CandidateEvent',payload_json:$event_json,payload_sha256:$event_sha,
 created_at:$created,source_type:'trusted_host_review',authority_ref:$authority,
 visibility:'PUBLIC',candidate_id:$candidate})
CREATE (c)-[:HAS_CANDIDATE_EVENT {id:$ce_id,tenant_id:$tenant,payload_json:$ce_json,payload_sha256:$ce_sha}]->(event)
CREATE (event)-[:PREVIOUS_EVENT {id:$pe_id,tenant_id:$tenant,payload_json:$pe_json,payload_sha256:$pe_sha}]->(previous)
CREATE (s)-[:COMMITS {id:$commit_id,tenant_id:$tenant,payload_json:$commit_json,payload_sha256:$commit_sha}]->(m)
SET h.payload_json=$head_json,h.payload_sha256=$head_sha,
    h.state='PUBLISHED',h.event_id=$event,h.sequence=$sequence,
    s.epoch=$next,s.payload_json=$state_json,s.payload_sha256=$state_sha
RETURN event.payload_sha256,s.epoch
'''
(Q/'Q07_publication_commit.cypher').write_text(q7)
q9='''// PROPOSED / NOT_EXECUTED. Authorized query/publication manifests only, never arbitrary client-provided ID.
MATCH (m)-[h:HAS_CHUNK]->(c:SnapshotChunk)
WHERE m.id=$manifest AND m.tenant_id=$tenant AND c.tenant_id=$tenant
RETURN h.id,h.payload_json,h.payload_sha256,c.id,c.chunk_index,c.payload_json,c.payload_sha256
ORDER BY c.chunk_index
LIMIT 129
'''
(Q/'Q09_document_chunks.cypher').write_text(q9)
p=D/'contracts/graph_v2_catalog.json';d=json.loads(p.read_text());d['per_label_required_native_projection']['LifecycleHead'].append('event_id');p.write_text(json.dumps(d,indent=2)+'\n')
rows=[]
for p in sorted(Q.glob('*.cypher')):
 rows.append({'file':p.name,'sha256':sha(p),'parameters':sorted(set(re.findall(r'\$([A-Za-z_][A-Za-z0-9_]*)',p.read_text()))),'execution_status':'TESTED_SYNTHETIC_SHAPE_ONLY' if p.name in ['Q04_evidence_paths.cypher','Q07_epoch_fence_probe.cypher'] else 'PROPOSED_NOT_EXECUTED'})
(D/'contracts/QUERY_CATALOG.json').write_text(json.dumps(rows,indent=2)+'\n')
p=D/'GRAPH_CYPHER_CONTRACTS.md';s=p.read_text();s+='\n## 可直接实施的完整模板边界\n\n`cypher/Q07_publication_commit.cypher`补齐共同节点/边payload、candidate-head关联、event_id与state native投影、epoch+1以及TenantState新payload SHA；上文缩写仅说明形态，以该完整模板为实现合同。所有state_json/head_json/edge JSON必须由Host canonical生成并逐项对照native字段，不接受Agent直接提供。`Q06_record_recommendation`为不提升证据epoch的派生记录；`Q09_document_chunks`核对实际HAS_CHUNK和chunk metadata。两者均PROPOSED/NOT_EXECUTED。生产权限/完整性/并发失败仍须G2-1/2动态验证，合成minimalfence不替代完整Q07。\n';p.write_text(s)
p=D/'test_design_contracts.py';shutil.copyfile(p,E/'source_audit/test_design_contracts.before_header_fix.py');s=p.read_text().replace("text.count('## ADR-')==13","len(re.findall(r'^## ADR-[0-9]+',text,re.M))==13");p.write_text(s)
print('FULL_QUERY_TEMPLATES_AND_EXACT_HEADER_CHECK_READY')
