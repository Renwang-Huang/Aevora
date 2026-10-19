"""Private Host execution after a sealed original native Outcome, never a public tool."""
from audit import *
import sys,copy,uuid
from datetime import datetime,timezone,timedelta
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.host_pins import read_registry
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome
from aevora_maintainer.host_v2 import TrustedHost
label=sys.argv[1];root=E/'04_live'/label;summary=json.loads((root/'ORIGINAL_RUN_SUMMARY.json').read_text());run=root/'runs'/summary['run_id']
report=json.loads((run/'evaluation_report.json').read_text());assert report.get('evaluation_result') in {'PASS','FAIL'},'No original independent Outcome'
assert (run/'run_evidence_manifest.json').is_file()
cases=json.loads((E/'02_source/cases/CASES.json').read_text())
anchor=TrustAnchor(run,sha(run/'run_evidence_manifest.json'),{'evaluation_report.json':run.name},profile='current_live',manifest_relative_path='run_evidence_manifest.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],source_manifest_relative_path='SOURCE_MANIFEST.json')
out=verify_outcome(anchor,'evaluation_report.json')
r=GraphRepository.from_environment();v=r.v2(TenantBinding('tenant-g23-live',r.graph_name),read_registry(E/'03_world_accepted/private_host_pins'))
grant=TrustedHost.bootstrap(v,E/'03_world_accepted/private_host_pins',principal='g23-native-outcome-operator',allowed_scope={},generation=uuid.uuid4().hex)
h=TrustedHost(v,E/'03_world_accepted/private_host_pins',grant);verifier=h.register_orderflow(anchor,out['evaluator_fingerprint'],out['test_suite_fingerprint'])
rows=r.query('MATCH(c:Candidate {run_id:$run}) RETURN c.id ORDER BY c.id',{'run':run.name});natural=[v.node(x[0]) for x in rows if v.node(x[0]).get('source_type')=='UNTRUSTED_AGENT']
write(root/'NATURAL_CANDIDATES.json',natural)
assert natural,'NATIVE_PROPOSAL_NOT_OBSERVED'
results=[]
for native in natural:
 p=native['body'];c=h.propose(p,run_id=run.name,tree_sha=out['candidate_tree_sha256'],patch_sha=out['patch_sha256'],origin='AGENT_PROPOSED',native_candidate_id=native['id'])
 s=h.verify_source(c['id'],verifier.authority_id,'evaluation_report.json');o=h.verify_outcome(c['id'],s['id'])
 # No edits to the natural principle or its necessary/exclusion conditions.
 # Restrict additional Host scope to the actual task and persistence type.
 from integrations.aevora import public_runtime_context
 observed=public_runtime_context(report['scenario_metadata'])
 approved=copy.deepcopy(p['scope'])
 for fact_key in ['shared_state_kind','concurrency_scope']:
  assert observed.get(fact_key) is not None
  approved['task.'+fact_key]=[observed[fact_key]]
 for key in ['task.shared_state_kind','task.concurrency_scope']:
  if key in p['scope']:assert all(x in p['scope'][key] for x in approved[key]),'Scope not observed, cannot widen'
 review=h.review(c['id'],s['id'],o['id'],approved_scope=approved,reason='Trusted operator reviewed the actual original patch and task semantics; independent original Oracle only certifies its bounded engineering outcome, not causal memory benefit')
 if review.get('verification')!='REVIEW_APPROVED':
  results.append(dict(status=review['status'],candidate=c,source=s,outcome=o,review=review));continue
 head=h.transition(c['id'],'PUBLISHING',expected_head=digest(h.head(c['id'])),reason='Verified native source and original independent Outcome')
 prepared=h.prepare(c['id'],review['id'],request_key='native:'+native['id'],expected_head=digest(head),expected_epoch=v.state()['epoch'])
 receipt=h.publish(prepared)
 result=dict(status='PUBLICATION_COMMITTED',candidate=c,source=s,outcome=o,review=review,receipt=receipt,run_id=run.name,original_outcome=out,source_seal_sha256=anchor.manifest_sha256)
 results.append(result)
write(root/'HOST_PUBLICATIONS.json',results)
accepted=[x for x in results if x['status']=='PUBLICATION_COMMITTED'];assert accepted,'Native candidate not admissible'
assert len(accepted)==1,'Multiple approved proposals require explicit independent selection review'
write(root/'HOST_PUBLICATION.json',accepted[0]);write(E/'04_live/S1_SELECTED.json',{'label':label,'run_id':run.name,'publication_sha256':sha(root/'HOST_PUBLICATION.json')})
write(root/'GRAPH_AFTER_HOST.json',{'nodes':r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id'),'edges':r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id'),'state':v.state()})
bootstrap=json.loads((E/'03_world_accepted'/(label+'_BOOTSTRAP.json')).read_text());bootstrap['grant'].update(session_id='capability-session-'+uuid.uuid4().hex,generation=uuid.uuid4().hex,authz_epoch=v.state()['authz_epoch'],valid_until=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat())
write(E/'03_world_accepted/S2_BOOTSTRAP.json',bootstrap);(E/'03_world_accepted/S2_BOOTSTRAP.json').chmod(0o600)
write(E/'04_live/S2_REGISTRATION.json',{'at':now(),'s1_label':label,'s1_run':run.name,'s1_official_session':summary['session_id'],'s1_publication_sha256':sha(root/'HOST_PUBLICATION.json'),'publication_receipt':accepted[0]['receipt'],'source_gate_sha256':sha(E/'G23_LIVE_GATE_V4.json'),'new_native_session_required':True,'task':'D/v01 new independent defective workspace and database','new_id_in_prompt':False,'prompt_change':False,'causal_benefit':'UNKNOWN'})
r.close();print(json.dumps({'status':'PUBLICATION_COMMITTED','source_actor':accepted[0]['source']['native_source']['proposal_actor_thread_id'],'receipt':accepted[0]['receipt']}))
