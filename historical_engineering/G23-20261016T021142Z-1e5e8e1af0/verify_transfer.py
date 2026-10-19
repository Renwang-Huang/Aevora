"""Audit real S2 bytes against actual S1 publication. No model invocation."""
from audit import *
from aevora.contracts import digest,decode
from datetime import datetime
sel=json.loads((E/'04_live/S1_SELECTED.json').read_text());root=E/'04_live'/sel['label'];pub=json.loads((root/'HOST_PUBLICATION.json').read_text());s1=json.loads((root/'ORIGINAL_RUN_SUMMARY.json').read_text());snap=json.loads((root/'GRAPH_AFTER_HOST.json').read_text());nodes=[decode(x[1],'tenant-g23-live') for x in snap['nodes']];revision=next(n for n in nodes if n['kind']=='ExperienceRevision' and n.get('candidate_id')==pub['candidate']['id']);exp=revision['experience_id']
S=E/'04_live/S2';s2=json.loads((S/'ORIGINAL_RUN_SUMMARY.json').read_text());assert s1['session_id']!=s2['session_id'] and s1['run_id']!=s2['run_id'];assert s2['integration_result']=='PASS' and s2['evaluation_result']=='PASS'
calls=json.loads((S/'MCP_EXACT_JOIN.json').read_text())['calls'];resolves=[];bundles=[];decisions=[]
for c in calls:
 if c['is_error'] or c['jsonrpc_error']:continue
 for b in c['result']:
  if c['tool']=='resolve_experience':
   for rec in b.get('recommendations',[]):
    if rec['experience_id']==exp:resolves.append((c,b,rec))
  if c['tool']=='build_evidence_bundle' and b.get('experience_id')==exp and b.get('status')=='AVAILABLE':bundles.append((c,b))
  if c['tool']=='record_decision' and c['arguments']['decision']['experience_id']==exp and b.get('status')=='RECORDED_UNTRUSTED':decisions.append((c,b))
assert resolves and bundles and decisions,'Missing actual new-Experience query/bundle/decision'
rc,rb,rec=resolves[0];pairs=[(c,b) for c,b in bundles if b['query_id']==rec['query_id'] and b.get('witness')];assert pairs,'Full witness bytes unavailable; do not infer completion from preview'
bc,bundle=pairs[-1];assert digest(bundle['witness'])==bundle['document_sha256']==rec['witness_sha256'];assert bundle['recommendation']['completeness']=='COMPLETE' and not bundle['recommendation']['integrity_issues'];assert revision['id'] in bundle['recommendation']['revision_ids'];dc,db=next((c,b) for c,b in decisions if c['arguments']['decision']['query_id']==rec['query_id']);assert dc['arguments']['decision']['decision'] in {'APPLY','VERIFY'}
run=S/'runs'/s2['run_id'];trace=[json.loads(l) for l in (run/'native_agent_trace.jsonl').read_text().splitlines()];actions=[e for e in trace if e['event_type']=='native.FileChange' and any('/app/' in k for k in e['payload']['event'].get('changes',{}))];assert actions,'No official code edit';first=min(actions,key=lambda e:e['timestamp']);ts=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
assert ts(rc['response_ref']['timestamp'])<=ts(bc['response_ref']['timestamp'])<=ts(dc['response_ref']['timestamp'])<ts(first['timestamp'])
assert rec['core_verdict'] in {'APPLY','VERIFY'}
result=dict(status='PASS_OBSERVED_TRANSFER_NOT_CAUSAL_BENEFIT',experience_id=exp,revision_ids=bundle['recommendation']['revision_ids'],s1_original_run=s1['run_id'],s1_official_session=s1['session_id'],s1_publication_sha256=sha(root/'HOST_PUBLICATION.json'),s1_q07_receipt=pub['receipt'],s2_original_run=s2['run_id'],s2_official_session=s2['session_id'],query_id=rec['query_id'],recommendation_id=rec['recommendation_id'],core_verdict=rec['core_verdict'],agent_decision=dc['arguments']['decision'],decision_id=db['decision_id'],actor=dc['actor'],query_ref=rc['response_ref'],complete_bundle_ref=bc['response_ref'],witness_sha256=rec['witness_sha256'],decision_ref=dc['response_ref'],first_observed_business_file_change=first,patch_sha256=s2['patch_sha256'],original_outcome=s2['evaluation_result'],original_report_sha256=s2['report_sha256'],native_children=s2['native_verified_count'],causal_benefit='UNKNOWN',strategy_alignment='INDEPENDENT_MAINTAINER_PATCH_REVIEW_REQUIRED; file bytes and guards retained',task_novelty='NEW_INDEPENDENT_D_V01_INSTANCE_NOT_UNSEEN_FAMILY')
write(S/'TRANSFER_VERIFICATION.json',result);print('S2_EXACT_NEW_EXPERIENCE_TRANSFER_PASS',exp)
