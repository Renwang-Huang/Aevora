"""Verify complete archived event line references and select actual key Cypher."""
from hashlib import sha256
import json
from scripts.aevora_h3_audit import archive,write,digest,now


def main():
    A=archive();timeline=json.loads((A/'g4/native-timeline/NATIVE_EVENT_TIMELINE.json').read_text())
    lines={};checked=0
    for event in timeline['events']:
        ref=event['raw_reference'];path=A/ref['file']
        if path not in lines:lines[path]=path.read_bytes().splitlines(keepends=True)
        assert sha256(lines[path][ref['line']-1]).hexdigest()==ref['sha256']
        checked+=1
    unique=set();queries=[]
    p=A/'g3/graph-checks/necessity_01/trusted_graph_commands.jsonl'
    for index,raw in enumerate(p.read_bytes().splitlines(keepends=True),1):
        row=json.loads(raw);cmd=row['command']
        if cmd[0] not in ('GRAPH.QUERY','GRAPH.RO_QUERY') or len(cmd)<3:continue
        statement=cmd[2]
        if len(statement)>4096 or statement in unique:continue
        if len(queries)>=16 and 'DELETE' not in statement:continue
        unique.add(statement)
        queries.append({'command':cmd[0],'actual_statement':statement,'status':row['status'],
            'started_at':row['started_at'],'raw_reference':{'file':str(p.relative_to(A)),'line':index,'sha256':sha256(raw).hexdigest(),'scope':'Full archived line including newline'}})
    assert any('DELETE' in q['actual_statement'] for q in queries)
    write(A/'g4/AUDIT_KEY_CYPHER.json',{'source':'Actual official SDK GRAPH.QUERY/RO_QUERY trace, not invented queries','raw_file_sha256':digest(p),'queries':queries,'not_included':'Complete replies and remaining queries stay in Full; this bounded selector preserves actual query bytes and raw line references.'})
    write(A/'g4/EVENT_REFERENCE_VERIFICATION.json',{'status':'PASS','at':now(),'complete_original_event_lines_checked':checked,'sessions':len(timeline['sessions']),
        'timeline_sha256':digest(A/'g4/native-timeline/NATIVE_EVENT_TIMELINE.json'),'actual_key_queries':len(queries),
        'qualification':'Verifies actual source line bytes; official original and MCP per-run identity have different visibility; no invented child authorship or total causal order.'})
    print(json.dumps({'status':'PASS','line_references_checked':checked,'key_queries':len(queries)}));return 0


if __name__=='__main__':raise SystemExit(main())
