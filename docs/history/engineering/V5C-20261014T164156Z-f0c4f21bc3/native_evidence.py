"""Read-only post-run indices with original byte references, not invented events."""
from pathlib import Path
import sys,json,hashlib,collections
E=Path(__file__).resolve().parent;sys.path.insert(0,str(E))
from audit import write,sha,now
phase=sys.argv[1];out=E/('02_live_s1' if phase=='s1' else '04_live_s2')
s=json.loads((out/'ORIGINAL_RUN_SUMMARY.json').read_text());run=out/'runs'/s['run_id'];m=json.loads((run/'runtime_metadata.json').read_text());report=json.loads((run/'evaluation_report.json').read_text())
def lines(name):
 p=run/name
 if not p.exists():return []
 return [(i,json.loads(b),{'file':str(p.relative_to(E)),'line':i,'sha256':hashlib.sha256(b).hexdigest(),'scope':'ORIGINAL_LINE_BYTES_WITH_NEWLINE'}) for i,b in enumerate(p.read_bytes().splitlines(keepends=True),1)]
requests={};timeline=[]
for i,e,ref in lines('aevora_mcp_events.jsonl'):
 if e.get('category')!='JSONRPC':continue
 msg=json.loads(e['raw_json']);key=(e.get('connection_id'),msg.get('id'))
 if e.get('direction')=='PARTICIPANT_TO_OFFICIAL_SDK' and msg.get('method')=='tools/call':
  row={'request_id':msg['id'],'connection_id':key[0],'tool':msg['params']['name'],'arguments':msg['params'].get('arguments'),'request_at':e['timestamp'],'request_reference':ref};requests[key]=row;timeline.append(row)
 elif e.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and key in requests:
  row=requests[key];result=msg.get('result',{});row.update(response_at=e['timestamp'],response_reference=ref,isError=result.get('isError',bool(msg.get('error'))),result=result.get('structuredContent'),error=msg.get('error'),content=result.get('content'))
with (out/'mcp_timeline.jsonl').open('x') as f:
 for row in timeline:f.write(json.dumps(row)+'\n')
typed=[];starts=[];terminal=[]
for i,e,ref in lines('codex_events.jsonl'):
 item=e.get('item',{})
 if e.get('type')=='thread.started':starts.append({'event':e,'reference':ref})
 if e.get('type') in ('turn.completed','turn.failed','error'):terminal.append({'event':e,'reference':ref})
 if item.get('type') in ('mcp_tool_call','file_change') or e.get('type') in ('thread.started','turn.completed','turn.failed'):typed.append({'event':e,'reference':ref})
with (out/'typed_event_index.jsonl').open('x') as f:
 for row in typed:f.write(json.dumps(row)+'\n')
gateway=[{'event':e,'reference':ref} for _,e,ref in lines('gateway_transport_events.jsonl')]
completed=[x for x in gateway if x['event']['event_type']=='REQUEST_FINISHED'];categories=collections.Counter(x['event']['detail'].get('category',x['event']['detail'].get('outcome')) for x in completed)
indices={n:{'path':str((run/n).relative_to(E)),'sha256':sha(run/n),'bytes':(run/n).stat().st_size} for n in ['codex_events.jsonl','aevora_mcp_events.jsonl','gateway_transport_events.jsonl','runtime_metadata.json','evaluation_report.json','submission.diff','run_evidence_manifest.json']}
write(out/'RAW_EVIDENCE_INDEX.json',{'run_id':run.name,'files':indices,'official_rollouts':[{'path':str(p.relative_to(E)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted((run/'artifacts/native_rollouts').rglob('*.jsonl'))]})
proposal=[x for x in timeline if x['tool']=='propose_experience'];decisions=[x for x in timeline if x['tool']=='record_decision']
write(out/'NATIVE_LIFECYCLE_RESULT.json',{'run_id':run.name,'session_id':m.get('session_id'),'thread_id':m.get('thread_id'),'native_exit':m.get('exit_code'),'fresh_session':m.get('fresh_session'),'agent_mode':m.get('agent_mode'),'subagents':report.get('agent',{}).get('subagents'),'starts':starts,'terminal':terminal,'natural_original_run':True,'runtime_result':report.get('runtime_result'),'submission_integrity_status':report.get('submission_integrity_status'),'evaluation_result':report.get('evaluation_result'),'integration_result':report.get('integration_result'),'overall_status':report['overall_status'],'test_count':report['test_results']['collected'],'test_pass':report['test_results']['passed'],'patch_sha256':sha(run/'submission.diff'),'tools':dict(collections.Counter(x['tool'] for x in timeline)),'tool_errors':[x for x in timeline if x.get('isError')],'decisions':decisions,'proposals':proposal,'upstream_forwards':len(completed),'gateway_outcomes':dict(categories),'request_budget':m.get('request_budget'),'timeout_seconds':m.get('timeout_seconds'),'causal_benefit':'UNKNOWN','at':now()})
print(phase,run.name,report['overall_status'],report['test_results']['passed'],len(proposal))
