"""Actual complete-line event references; no prose-inferred Agent relations."""
import json
from hashlib import sha256
from scripts.aevora_h3_audit import archive,write,now


def main():
    A=archive();out=A/'g4/native-timeline';out.mkdir(parents=True,mode=0o700)
    rows=[];sessions=[]
    def relationship(a):
        value={k:a.get(k,'UNAVAILABLE') for k in ['agent_id','agent_path','parent_thread_id','verified','completed','execution_verified','session_matched']}
        value['evidence']={k:{field:record[field] for field in ['raw_reference','communication_reference','timestamp','turn_id'] if field in record}
            for k in ['spawn','task_delivery','completion','parent_receipt'] if isinstance((record:=a.get(k)),dict)}
        return value
    for gate in ['g1','g2','g3']:
        for run in sorted((A/gate).glob('**/runs/*')):
            meta=run/'runtime_metadata.json'
            if not meta.exists():continue
            m=json.loads(meta.read_text());session={'run_id':run.name,'thread_id':m.get('thread_id','UNAVAILABLE'),
                'runtime_result':m.get('runtime_result'),'failure_kind':m.get('failure_kind'),
                'evaluation_result':m.get('evaluation_result','NOT_EXECUTED_OR_NOT_APPLICABLE'),
                'native_children':[relationship(x) for x in m.get('subagents',{}).get('agents',[])],
                'source':'ACTUAL_RUNTIME_METADATA_AND_MATCHED_NATIVE_ROLLOUTS','elapsed_seconds':m.get('elapsed_seconds','UNAVAILABLE')}
            sessions.append(session)
            for name in ['codex_events.jsonl','aevora_mcp_events.jsonl','gateway_transport_events.jsonl']:
                p=run/name
                if not p.exists():continue
                for line,raw in enumerate(p.read_bytes().splitlines(keepends=True),1):
                    ref={'file':str(p.relative_to(A)),'line':line,'sha256':sha256(raw).hexdigest(),'sha256_scope':'ACTUAL_ARCHIVED_BYTES_INCLUDING_NEWLINE'}
                    try:e=json.loads(raw)
                    except ValueError:
                        rows.append({'run_id':run.name,'kind':'MALFORMED_ORIGINAL_LINE','raw_reference':ref});continue
                    item=e.get('item',{})
                    # No text extraction, invented timestamps, identity or
                    # completion: all values are present typed event fields.
                    rows.append({'run_id':run.name,'source_file':name,'kind':e.get('type',e.get('category',e.get('event',e.get('kind','UNAVAILABLE')))),
                        'timestamp':e.get('timestamp',e.get('started_at','UNAVAILABLE')),
                        'timestamp_scope':'ACTUAL_EVENT_FIELD_OR_UNAVAILABLE','item_type':item.get('type','UNAVAILABLE'),
                        'item_id':item.get('id','UNAVAILABLE'),'tool':item.get('tool',e.get('tool','UNAVAILABLE')),
                        'status':item.get('status',e.get('status','UNAVAILABLE')),'connection_id':e.get('connection_id','UNAVAILABLE'),
                        'raw_reference':ref})
    write(out/'NATIVE_EVENT_TIMELINE.json',{'sessions':sessions,'events':rows,'recorded_at':now(),
        'ordering':'Each source retains original line sequence. Different files do not establish a total causal order.',
        'agent_identity':'Only actually verified native metadata relations; MCP connection identity is not individual Agent identity.'})
    write(out/'RESULT.json',{'status':'PASS','actual_sessions':len(sessions),'raw_event_references':len(rows),'causal_benefit':'UNKNOWN'})
    print(json.dumps({'status':'PASS','sessions':len(sessions),'events':len(rows)}));return 0


if __name__=='__main__':raise SystemExit(main())
