// FROZEN G22 HANDOFF; NOT IMPLEMENTED/EXECUTED/ACCEPTED AS A PRODUCTION PUBLISHER.
// Host must validate canonical prepared_json and every supplied pin from source/outcome/review.
// Parameters never originate from a public MCP tool. G22 must add audited native head projections.
MATCH (s:TenantState {id:$state,tenant_id:$tenant}),
      (c:Candidate {id:$candidate,tenant_id:$tenant})-[:HAS_LIFECYCLE]->(head:LifecycleHead {id:$head,tenant_id:$tenant}),
      (previous:CandidateEvent {id:$previous,tenant_id:$tenant}),
      (prepared:SourceVerification {id:$prepared,tenant_id:$tenant}),
      (source:SourceVerification {id:$source,tenant_id:$tenant}),
      (outcome:VerifiedOutcome {id:$outcome,tenant_id:$tenant}),
      (authority:Authority {id:$authority,tenant_id:$tenant}),
      (manifest:PublicationManifest {id:$manifest,tenant_id:$tenant})
WHERE s.epoch=$expected_epoch AND s.authz_epoch=$expected_authz_epoch
  AND s.generation=$generation AND $next_epoch=$expected_epoch+1
  AND s.payload_json=$expected_state_json AND s.payload_sha256=$expected_state_sha
  AND head.payload_sha256=$expected_head AND head.payload_json=$expected_head_json
  AND head.state='PUBLISHING' AND head.candidate_id=$candidate AND head.event_id=$previous
  AND previous.candidate_id=$candidate AND previous.payload_sha256=$previous_sha
  AND c.payload_sha256=$candidate_sha AND c.payload_json=$candidate_json
  AND prepared.payload_sha256=$prepared_sha AND prepared.payload_json=$prepared_json
  AND source.payload_sha256=$source_sha AND source.payload_json=$source_json
  AND outcome.payload_sha256=$outcome_sha AND outcome.payload_json=$outcome_json
  AND authority.payload_sha256=$authority_sha AND authority.payload_json=$authority_json
  AND authority.state='ACTIVE'
  AND manifest.payload_sha256=$manifest_sha AND manifest.payload_json=$manifest_json
  AND manifest.epoch=$next_epoch
OPTIONAL MATCH (manifest)-[chunk_edge:HAS_CHUNK]->(chunk:SnapshotChunk)
WITH s,c,head,previous,prepared,source,outcome,authority,manifest,chunk_edge,chunk
ORDER BY chunk.chunk_index
WITH s,c,head,previous,prepared,source,outcome,authority,manifest,
     collect([chunk.id,chunk.payload_sha256,chunk_edge.id,chunk_edge.payload_sha256,chunk.chunk_index,chunk.tenant_id]) AS chunks
WHERE chunks=$prepared_chunk_pins
CREATE (event:CandidateEvent {id:$event,tenant_id:$tenant,record_version:$record_version,
 kind:'CandidateEvent',created_at:$created,source_type:'trusted_host_review',authority_ref:$authority,
 visibility:'PUBLIC',payload_json:$event_json,payload_sha256:$event_sha,candidate_id:$candidate})
CREATE (c)-[:HAS_CANDIDATE_EVENT {id:$candidate_edge,tenant_id:$tenant,record_version:$record_version,
 kind:'HAS_CANDIDATE_EVENT',created_at:$created,source_type:'trusted_host_review',authority_ref:$authority,
 visibility:'PUBLIC',payload_json:$candidate_edge_json,payload_sha256:$candidate_edge_sha,
 source_id:$candidate,source_kind:'Candidate',target_id:$event,target_kind:'CandidateEvent'}]->(event)
CREATE (event)-[:PREVIOUS_EVENT {id:$previous_edge,tenant_id:$tenant,record_version:$record_version,
 kind:'PREVIOUS_EVENT',created_at:$created,source_type:'trusted_host_review',authority_ref:$authority,
 visibility:'PUBLIC',payload_json:$previous_edge_json,payload_sha256:$previous_edge_sha,
 source_id:$event,source_kind:'CandidateEvent',target_id:$previous,target_kind:'CandidateEvent'}]->(previous)
CREATE (s)-[:COMMITS {id:$commit_edge,tenant_id:$tenant,record_version:$record_version,
 kind:'COMMITS',created_at:$created,source_type:'trusted_host_review',authority_ref:$authority,
 visibility:'PUBLIC',payload_json:$commit_json,payload_sha256:$commit_sha,
 source_id:$state,source_kind:'TenantState',target_id:$manifest,target_kind:'PublicationManifest'}]->(manifest)
SET head.payload_json=$new_head_json,head.payload_sha256=$new_head_sha,
    head.state='PUBLISHED',head.event_id=$event,head.sequence=$next_sequence,
    s.payload_json=$new_state_json,s.payload_sha256=$new_state_sha,s.epoch=$next_epoch
RETURN event.id,event.payload_sha256,s.epoch,s.authz_epoch
