from audit import *
import sys
label=sys.argv[1];root=E/'04_live'/label;summary=json.loads((root/'ORIGINAL_RUN_SUMMARY.json').read_text());run=root/'runs'/summary['run_id'];p=run/'aevora_mcp_events.jsonl';pending={};calls=[]
for i,raw in enumerate(p.read_bytes().splitlines(keepends=True),1):
 e=json.loads(raw)
 if e.get('category')!='JSONRPC':continue
 j=json.loads(e['raw_json']);ref=dict(file=str(p.relative_to(E)),line=i,sha256=__import__('hashlib').sha256(raw).hexdigest(),archived_message_sha256=e.get('archived_message_sha256'),timestamp=e.get('timestamp'));key=(e['connection_id'],str(j.get('id')))
 if e.get('direction')=='PARTICIPANT_TO_OFFICIAL_SDK' and j.get('method')=='tools/call':pending[key]=(j,ref)
 elif e.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and key in pending:
  req,rr=pending.pop(key);result=j.get('result',{});parsed=[]
  for block in result.get('content',[]):
   if block.get('type')=='text':
    try:parsed.append(json.loads(block['text']))
    except (ValueError,TypeError):parsed.append({'unparsed_text':block['text']})
  meta=req['params'].get('_meta',{}).get('x-codex-turn-metadata',{})
  calls.append(dict(tool=req['params']['name'],arguments=req['params'].get('arguments'),actor=meta.get('thread_id','UNAVAILABLE'),official_session=meta.get('session_id','UNAVAILABLE'),official_turn=meta.get('turn_id','UNAVAILABLE'),connection_id=key[0],request_id=key[1],request_ref=rr,response_ref=ref,result=parsed,jsonrpc_error=j.get('error'),is_error=result.get('isError',False)))
write(root/'MCP_EXACT_JOIN.json',{'classification':'OBSERVED_ORIGINAL_MCP_BYTES_NOT_INVENTED_TOOL_EVENTS','run_id':run.name,'session_id':summary['session_id'],'calls':calls,'unanswered_requests':len(pending)})
for c in calls:
 print(c['tool'],c['actor'],c['request_ref']['timestamp'],str(c['result'])[:800])
