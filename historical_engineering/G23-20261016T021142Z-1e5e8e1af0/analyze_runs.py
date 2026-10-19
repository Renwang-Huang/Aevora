"""Read closed original runs; correction output stays outside every sealed Run."""
from audit import *
import csv
from integrations.native_rollout_trace import analyze_native_rollouts
out=E/'analysis';out.mkdir(exist_ok=True);timeline=[];summaries=[]
for phase in sorted((E/'04_live').iterdir()):
 if not phase.is_dir() or not (phase/'ORIGINAL_RUN_SUMMARY.json').is_file():continue
 original=json.loads((phase/'ORIGINAL_RUN_SUMMARY.json').read_text());run=phase/'runs'/original['run_id'];meta=json.loads((run/'runtime_metadata.json').read_text())
 if not meta.get('ended_at'):continue
 a=analyze_native_rollouts(run.name,run,meta.get('native_rollouts',{}),expected_parent_thread_id=meta.get('thread_id'))
 write(out/(phase.name+'-official-analysis.json'),{'classification':'POST_COLLECTION_CURRENT_PARSER_REVIEW_NOT_ORIGINAL_GRADE_REWRITE','parser_sha256':sha(P/'integrations/native_rollout_trace.py'),'original_metadata_sha256':sha(run/'runtime_metadata.json'),'analysis':a})
 parents={x['agent_id']:x['parent_thread_id'] for x in a['summary']['subagents']['agents']}
 for e in a['events']:
  p=e['payload'];ref=p['raw_reference'];timeline.append({'attempt':phase.name,'run_id':run.name,'official_session_id':a['summary']['session_id'],'actor_thread_id':p['thread_id'],'parent_thread_id':parents.get(p['thread_id'],'UNAVAILABLE'),'event_type':e['event_type'],'timestamp':e['timestamp'],'raw_file':ref['path'],'raw_line':ref['line'],'raw_line_sha256':ref['sha256'],'origin':'OFFICIAL_OWN_TURN_RECORD_NOT_PROSE','event_body_sha256':__import__('hashlib').sha256(json.dumps(p['event'],sort_keys=True).encode()).hexdigest()})
 summaries.append({'attempt':phase.name,'run_id':run.name,'official_session_id':meta.get('session_id'),'original_runtime':original['runtime_result'],'original_evaluation':original['evaluation_result'],'original_integration':original['integration_result'],'original_multi':original.get('multi_agent_result'),'original_verified_children':original.get('native_verified_count'),'current_parser_verified_children':a['summary']['subagents']['verified_count'],'original_report_sha256':original['report_sha256'],'patch_sha256':original.get('patch_sha256'),'proposal_completed':sum(e['event_type']=='native.McpToolCall' and e['payload']['event'].get('tool')=='propose_experience' and e['payload']['event'].get('status')=='completed' for e in a['events']),'upstream_requests':original.get('upstream_requests')})
if timeline:
 with (out/'G23_AGENT_IDENTITY_AND_TOOL_TIMELINE.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(timeline[0]));w.writeheader();w.writerows(timeline)
if summaries:
 with (out/'G23_ORIGINAL_RUN_OUTCOME_MATRIX.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
print('closed original runs',len(summaries),'official events',len(timeline))
