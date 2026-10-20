"""Tamper negatives derived from actual sealed native input, not new Agent runs."""
from audit import *
from integrations.native_rollout_trace import analyze_native_rollouts
from aevora_maintainer.native_source import join_proposal
from aevora.contracts import V2Error
import copy
root=E/'04_live/S1_04';s=json.loads((root/'ORIGINAL_RUN_SUMMARY.json').read_text());run=root/'runs'/s['run_id'];m=json.loads((run/'runtime_metadata.json').read_text());p=analyze_native_rollouts(run.name,run,m['native_rollouts'],expected_parent_thread_id=m['thread_id']);broker=[json.loads(l) for l in (run/'aevora_mcp_events.jsonl').read_text().splitlines()];natural=json.loads((root/'NATURAL_CANDIDATES.json').read_text());eligible={p['summary']['thread_id']}|{a['agent_id'] for a in p['summary']['subagents']['agents'] if a['verified']};checks=[]
for n in natural:
 args=dict(run_id=run.name,candidate_id=n['id'],body_sha256=n['body_sha256'],eligible_actors=eligible,expected_tenant='tenant-g23-live');valid=join_proposal(p['events'],broker,**args);assert valid
 checks.append(dict(name='EXACT_REAL_NATIVE_SOURCE_POSITIVE',candidate=n['id'],actor=valid[0]['actor_thread_id'],actual='ACCEPTED'))
 for key,value in [('expected_tenant','tenant-foreign'),('eligible_actors',{'forged-only'}),('candidate_id','Candidate:'+'0'*64),('body_sha256','0'*64),('run_id','foreign-run')]:
  altered={**args,key:value}
  try:join_proposal(p['events'],broker,**altered);raise AssertionError('Source confusion accepted:'+key)
  except V2Error as e:assert e.code=='SOURCE_MISMATCH';checks.append(dict(name='ACTUAL_SOURCE_NEGATIVE_'+key,candidate=n['id'],actual=e.code))
write(E/'05_controls/ACTUAL_NATIVE_SOURCE_NEGATIVES.json',dict(status='PASS',classification='HOST_CONTROLLED_TAMPER_NEGATIVE_USING_REAL_ORIGINAL_NATIVE_RECORDS_NOT_NEW_AGENT_EXECUTION',run_id=run.name,input_runtime_sha256=sha(run/'runtime_metadata.json'),input_broker_sha256=sha(run/'aevora_mcp_events.jsonl'),checks=checks,source_code_sha256=sha(P/'aevora_maintainer/native_source.py')));print('ACTUAL_SOURCE_POSITIVES_AND_TAMPER_NEGATIVES_PASS',len(checks))
