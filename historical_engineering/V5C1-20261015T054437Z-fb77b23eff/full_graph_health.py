"""Actual SAME live graph public health; no pruning, no model request."""
from pathlib import Path
import sys,os,json,uuid,tempfile,secrets
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.mcp_broker import MCPBroker,MAX_MESSAGE_BYTES
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION,digest
from integrations.aevora import public_runtime_context
from scripts.aevora_h2_security import RPCClient
from scripts.aevora_h2_graph_e2e import RawCommands
phase=sys.argv[1];assert phase.replace('_','').isalnum()
out=E/'05_graph'/phase;out.mkdir();r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r)

def reconstruct(entries):
 root=None
 for row in entries:
  parts=[s.replace('~1','/').replace('~0','~') for s in row['pointer'].split('/')[1:]]
  value={} if row.get('container')=='object' else [None]*row['length'] if row.get('container')=='array' else row.get('value')
  if not parts:
   if 'string_offset' in row:
    assert row['string_offset']==len(root or '');root=(root or '')+value
   else:root=value
   continue
  parent=root
  for part in parts[:-1]:parent=parent[int(part)] if isinstance(parent,list) else parent[part]
  key=int(parts[-1]) if isinstance(parent,list) else parts[-1]
  if 'string_offset' in row:
   old=parent[key] if isinstance(parent,list) else parent.get(key);assert row['string_offset']==len(old or '');value=(old or '')+value
  parent[key]=value
 return root
try:
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'graph_before.json',before)
 facts=public_runtime_context(json.loads((E/'owned_runtime/source/benchmark/scenarios/D-V02/public.json').read_text()));observed=[]
 with tempfile.TemporaryDirectory(prefix='v5c1-health-') as td:
  token=secrets.token_hex(32);b=MCPBroker(run_id='v5c1-health-'+uuid.uuid4().hex,public_context=facts,socket_path=Path(td)/'mcp.sock',run_token=token,event_path=out/'mcp.jsonl',enable_proposals=True,request_timeout=120)
  with b:
   c=RPCClient(b,token,out/'client.jsonl');c.channel.settimeout(120);c.initialize()
   try:
    response=c.tool('resolve_experience',{'task_context':{}});assert response and not response['result'].get('isError');page=response['result']['structuredContent'];qid=page['query_id'];index=[];pages=0
    while True:
     index+=page['candidates'];pages+=1
     if not page['has_more']:break
     response=c.tool('resolve_experience',{'task_context':{},'cursor':page['next_cursor']});assert response and not response['result'].get('isError');page=response['result']['structuredContent']
    assert [v['experience_id'] for v in index]==r.experience_ids()
    write(out/'complete_candidate_index.json',{'query_id':qid,'candidates':index,'pages':pages})
    for item in index:
     eid=item['experience_id']
     for view in ['bundle','candidate']:
      args={'experience_id':eid,'query_id':qid,'view':view};reply=c.tool('build_evidence_bundle',args);assert reply and not reply['result'].get('isError');part=reply['result']['structuredContent'];count=1
      if part.get('projection')=='LOSSLESS_JSON_POINTER_ENTRIES':
       wanted=part['document_sha256'];entries=[]
       while True:
        entries+=part['entries']
        if not part['has_more']:break
        reply=c.tool('build_evidence_bundle',{**args,'cursor':part['next_cursor']});assert reply and not reply['result'].get('isError');part=reply['result']['structuredContent'];count+=1
       document=reconstruct(entries);assert digest(document)==wanted
      else:document={k:v for k,v in part.items() if k not in {'projection_version','truncated','has_more','next_cursor'}}
      if view=='candidate':
       assert digest(document)==item['full_candidate_sha256']
       assert document['decision']==item['decision'] and document['retrieval_snapshot_sha256']==item['retrieval_snapshot_sha256']
      observed.append({'experience_id':eid,'view':view,'pages':count,'full_document_sha256':digest(document),'counterexample_count':len(document.get('counterexample_paths',document.get('evidence_bundle',{}).get('counterexample_paths',[])))})
   finally:c.close()
  write(out/'cleanup.json',b.metadata)
 events=[json.loads(s) for s in (out/'mcp.jsonl').read_text().splitlines()];sizes=[len(v['raw_json'].encode()) for v in events if v.get('direction')=='OFFICIAL_SDK_TO_PARTICIPANT' and 'raw_json' in v]
 assert not b.metadata['rejections'] and max(sizes)<MAX_MESSAGE_BYTES
 after=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'graph_after.json',after)
 oldnodes={v[1]:v for v in before['nodes']};newnodes={v[1]:v for v in after['nodes']};oldedges={v[2]:v for v in before['edges']};newedges={v[2]:v for v in after['edges']}
 assert all(newnodes.get(k)==v for k,v in oldnodes.items()) and all(newedges.get(k)==v for k,v in oldedges.items())
 write(out/'RESULT.json',{'status':'PASS','at':now(),'graph':r.graph_name,'phase':phase,'nodes_before':before['node_count'],'edges_before':before['edge_count'],'nodes_after_query':after['node_count'],'edges_after_query':after['edge_count'],'candidate_count':len(index),'index_pages':pages,'complete_details':observed,'max_actual_wire_bytes':max(sizes),'all_response_wire_bytes':sizes,'transport_limit_bytes':MAX_MESSAGE_BYTES,'all_original_nodes_edges_preserved':True,'model_requests':0,'actor':'TRUSTED_HOST_REAL_PUBLIC_MCP_HEALTH_PROBE_NOT_AGENT','causal_benefit':'UNKNOWN'})
 print('SAME_FULL_GRAPH_HEALTH_PASS',phase,len(index),max(sizes),flush=True)
finally:raw.close();r.close()
