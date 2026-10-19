// PROPOSED / NOT_EXECUTED full lifecycle activation; preparation validates every canonical record/edge.
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
