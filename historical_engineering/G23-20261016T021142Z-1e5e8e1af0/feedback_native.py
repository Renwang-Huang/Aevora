"""Host-trusted follow-up from S2's original Oracle, never participant self-score."""
from audit import *
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.host_pins import read_registry
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora_maintainer.host_v2 import TrustedHost
import uuid,copy
selected=json.loads((E/'04_live/S1_SELECTED.json').read_text());pub=json.loads((E/'04_live'/selected['label']/'HOST_PUBLICATION.json').read_text());s2=E/'04_live/S2';summary=json.loads((s2/'ORIGINAL_RUN_SUMMARY.json').read_text());run=s2/'runs'/summary['run_id'];join=json.loads((s2/'TRANSFER_VERIFICATION.json').read_text());assert join['status']=='PASS_OBSERVED_TRANSFER_NOT_CAUSAL_BENEFIT';assert join['original_outcome']=='PASS'
exp=join['experience_id'];r=GraphRepository.from_environment();v=r.v2(TenantBinding('tenant-g23-live',r.graph_name),read_registry(E/'03_world_accepted/private_host_pins'));before=dict(nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id'));write(s2/'GRAPH_BEFORE_FEEDBACK.json',before)
cases=json.loads((E/'02_source/cases/CASES.json').read_text());anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],source_manifest_relative_path='SOURCE_MANIFEST.json');out=verify_outcome(anchor,'evaluation_report.json');assert out['run_id']==run.name and out['verdict']=='PASS'
grant=TrustedHost.bootstrap(v,E/'03_world_accepted/private_host_pins',principal='g23-s2-trusted-feedback-operator',allowed_scope={},generation=uuid.uuid4().hex);h=TrustedHost(v,E/'03_world_accepted/private_host_pins',grant);verifier=h.register_orderflow(anchor,out['evaluator_fingerprint'],out['test_suite_fingerprint'])
# Authenticate any actual S2 natural candidate as an additional independent
# Native source fact. Do not silently rewrite its wording into S1's principle.
if not (s2/'NATURAL_SOURCE_ADMISSION.json').exists():
 native_rows=r.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id',{'run':run.name});admissions=[]
 for row in native_rows:
  n=v.node(row[0])
  if n.get('source_type')!='UNTRUSTED_AGENT':continue
  nc=h.propose(n['body'],run_id=run.name,tree_sha=out['candidate_tree_sha256'],patch_sha=out['patch_sha256'],origin='AGENT_PROPOSED',native_candidate_id=n['id'])
  ns=h.verify_source(nc['id'],verifier.authority_id,'evaluation_report.json');no=h.verify_outcome(nc['id'],ns['id']);nr=h.review(nc['id'],ns['id'],no['id'],approved_scope=n['body']['scope'],reason='Independent source and original S2 Oracle validated; natural wording retained. Separate Host follow-up below preserves exact S1 principle bytes.')
  admissions.append(dict(candidate=nc,source=ns,outcome=no,review=nr,publication='NOT_PUBLISHED_AS_NEW_PRINCIPLE'))
 write(s2/'NATURAL_SOURCE_ADMISSION.json',admissions)
else:
 admissions=json.loads((s2/'NATURAL_SOURCE_ADMISSION.json').read_text());assert admissions and all(v.node(a['source']['id'])==a['source'] and v.node(a['outcome']['id'])==a['outcome'] for a in admissions)
# Re-attest the same bounded principle with NEW independent evidence. This is
# Host-authored feedback; do not label it a natural S2 proposal.
body=copy.deepcopy(pub['candidate']['body']);body['candidate_key']='host-feedback-'+run.name;body['source_references']=[];body['public_summary']='Trusted Host follow-up of an actual fresh Session, original hidden Oracle and observed same-Experience decision/action. Causal benefit remains UNKNOWN; not an additional natural Agent proposal.'
c=h.propose(body,run_id=run.name,tree_sha=out['candidate_tree_sha256'],patch_sha=out['patch_sha256'],origin='HOST_SEEDED');source=h.verify_source(c['id'],verifier.authority_id,'evaluation_report.json');outcome=h.verify_outcome(c['id'],source['id']);review=h.review(c['id'],source['id'],outcome['id'],approved_scope=pub['review']['approved_scope'],reason='Host reviewed the S2 original patch, exact new-Experience decision and independently pinned Oracle; append bounded follow-up, attribution UNKNOWN')
assert review.get('verification')=='REVIEW_APPROVED';oldrev=join['revision_ids'];assert oldrev
head=h.transition(c['id'],'PUBLISHING',expected_head=digest(h.head(c['id'])),reason='Actual S2 independent engineering Outcome supports bounded principle, not causal attribution');prepared=h.prepare(c['id'],review['id'],request_key='s2-real-feedback:'+run.name,expected_head=digest(head),expected_epoch=v.state()['epoch'],experience_id=exp,supersedes=oldrev);receipt=h.publish(prepared)
after=dict(nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id'));write(s2/'GRAPH_AFTER_FEEDBACK.json',after);write(s2/'HOST_TRUSTED_FEEDBACK.json',dict(classification='HOST_TRUSTED_FOLLOWUP_NOT_NATURAL_AGENT_PROPOSAL',status='PUBLICATION_COMMITTED',experience_id=exp,original_s1_publication_sha256=sha(E/'04_live'/selected['label']/'HOST_PUBLICATION.json'),new_original_run=run.name,source=source,outcome=outcome,review=review,receipt=receipt,causal_attribution='UNKNOWN',before_sha256=digest(before),after_sha256=digest(after)));print('TRUSTED_S2_FOLLOWUP_Q07_COMMITTED');r.close()
