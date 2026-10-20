"""Real graph interventions on a private owned copy, never new Agent outcomes."""
from audit import *
from aevora.contracts import *
from aevora.graph_repository import GraphRepository
from aevora.host_pins import read_registry
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from aevora_maintainer.host_v2 import TrustedHost
from tools.validation.g21_fixture import bulk
import uuid,copy,shutil
selected=json.loads((E/'04_live/S1_SELECTED.json').read_text());pub=json.loads((E/'04_live'/selected['label']/'HOST_PUBLICATION.json').read_text());snapshot=json.loads((E/'04_live'/selected['label']/'GRAPH_AFTER_HOST.json').read_text())
O=E/'05_controls/native-source-copy-2';O.mkdir(parents=True);pins=O/'private_host_pins';shutil.copytree(E/'03_world_accepted/private_host_pins',pins)
m=GraphRepository.from_environment();kw=m._client.connection.connection_pool.connection_kwargs;m.close();name='aevora_v2_g23_controls_'+uuid.uuid4().hex
r=GraphRepository(host='127.0.0.1',port=kw['port'],password=kw['password'],graph_name=name);v=r.v2(TenantBinding('tenant-g23-live',name),read_registry(pins));v.initialize()
ns=[decode(x[1],v.tenant) for x in snapshot['nodes']];es=[decode(x[2],v.tenant) for x in snapshot['edges']];old=[x for x in ns if x['kind']=='TenantState'];assert len(old)==1
r.query('MATCH(s:TenantState {id:$id}) SET s=$row',dict(id=v.state_id,row=native(old[0])),read_only=False);bulk(v,[n for n in ns if n['kind']!='TenantState'],es)
grant=TrustedHost.bootstrap(v,pins,principal='g23-controls',allowed_scope={},generation=uuid.uuid4().hex);h=TrustedHost(v,pins,grant)
revs=[n for n in ns if n['kind']=='ExperienceRevision' and n.get('candidate_id')==pub['candidate']['id']];assert len(revs)==1;exp=revs[0]['experience_id'];facts=pub['review']['facts'];checks=[]
def snap(label):
 nodes=r.query('MATCH(n) RETURN labels(n),properties(n) ORDER BY n.id');edges=r.query('MATCH(a)-[e]->(b) RETURN a.id,type(e),properties(e),b.id ORDER BY e.id');write(O/(label+'.json'),dict(nodes=nodes,edges=edges,sha256=digest([nodes,edges]),classification='HOST_CONTROLLED_GRAPH_TEST_FROM_REAL_NATIVE_SOURCE'));return nodes,edges
original=r.query
raw=O/'RAW_CYPHER.jsonl'
def query(statement,params=None,*,read_only=True):
 result=None
 try:result=original(statement,params,read_only=read_only);return result
 finally:
  with raw.open('a') as f:f.write(canonical_json(dict(statement=statement,params=params or {},read_only=read_only,rows=result))+'\n')
r.query=query

def resolve(label,fs):
 state,rows=resolve_v2(v,fs,'query:g23-control:'+label,utc_now());write(O/(label+'-recommendations.json'),{'state':state,'rows':rows,'classification':'HOST_CONTROLLED_GRAPH_TEST'});return next(rec['core_verdict'] for rec,wit in rows if rec['experience_id']==exp),rows
snap('before')
verdict,rows=resolve('apply',facts);assert verdict=='APPLY';checks.append(dict(name='APPLY_REAL_NATIVE_SOURCE',actual=verdict))
u=copy.deepcopy(facts);f=u['task.shared_state_kind'];f.update(availability='UNKNOWN',value=None,authority_class=None,authority_ref=None,source_refs=[],observed_at=None)
verdict,_=resolve('verify-unknown',u);assert verdict=='VERIFY';checks.append(dict(name='VERIFY_UNKNOWN_PREMISE',actual=verdict))
changed=copy.deepcopy(facts);key='task.concurrency_scope';doc=O/'declared-counter-context.json';write(doc,{'classification':'HOST_CONTROLLED_TASK_DECLARATION_NOT_ACTUAL_AGENT_RUN',key:'single_process_threads'})
f=changed[key];f.update(value='single_process_threads',authority_ref=grant.capability_id,authority_class='HOST_DECLARED_TASK',observed_at=now(),source_refs=[dict(file='declared-counter-context.json',file_sha256=sha(doc),line=1,line_sha256=__import__('hashlib').sha256(doc.read_bytes().splitlines(keepends=True)[0]).hexdigest(),byte_scope='ARCHIVED_BYTES_INCLUDING_NEWLINE')]);h.pins.put('fact_sources',digest(f),grant.capability_id)
verdict,_=resolve('abstain-outside-scope',changed);assert verdict=='ABSTAIN';checks.append(dict(name='ABSTAIN_DOMAIN_MISMATCH',actual=verdict))
# Delete and restore only a disposable copy's actual decisive edge. Main stays untouched.
state=v.state();w=v.read_witness(exp,state);edge_record=next(e for e in w['edges'].values() if e['kind']=='SUPPORTED_BY' and e['source_id']==revs[0]['id'])
r.query('MATCH()-[e:SUPPORTED_BY {id:$id}]->() DELETE e',{'id':edge_record['id']},read_only=False)
try:resolve('cut-support',facts);raise AssertionError('Missing decisive edge was accepted')
except V2Error as err:checks.append(dict(name='GRAPH_INTERVENTION_CUT',actual=err.code))
snap('cut');v.put_edge(edge_record);verdict,_=resolve('restored-support',facts);assert verdict=='APPLY';checks.append(dict(name='GRAPH_INTERVENTION_RESTORE',actual=verdict))
from aevora_core.tests.g22.test_sdk_and_boundaries import sdk
from aevora_core.tests.test_mcp_real_graph import connect,tool
import pytest
mp=pytest.MonkeyPatch();mp.setenv('AEVORA_G22_ARTIFACT_ROOT',str(O/'sdk-artifacts'))
b,t=sdk(h,facts,O,mp)
with b:
 conn,stream=connect(b,t)
 try:
  q=tool(conn,stream,2,'resolve_experience',{'task_context':{}});assert not q.get('isError');q=q['structuredContent'];rec=next(x for x in q['recommendations'] if x['experience_id']==exp);assert rec['core_verdict']=='APPLY'
  cached=tool(conn,stream,3,'build_evidence_bundle',dict(query_id=q['query_id'],experience_id=exp,view='recommendation'));assert not cached.get('isError')
  prepared=h.prepare_authority_withdrawal(pub['source']['outcome_authority_id'],reason='Controlled revocation of real source verifier, not source erasure',request_key='g23-source-withdrawal',expected_epoch=v.state()['epoch'])
  receipt=h.commit_authority_withdrawal(prepared);verdict,revoked_rows=resolve('revoked-authority',facts)
  target=next(rec for rec,w in revoked_rows if rec['experience_id']==exp)
  # Q07 withdraws support authority, not the rule/revision itself. The inherited
  # documented policy is VERIFY when all complete applicable support is gone.
  assert verdict=='VERIFY' and target['reason_codes']==['NO_COMPLETE_APPLICABLE_SUPPORT']
  assert exp in receipt['affected_experience_ids'] and receipt['authz_epoch']==state['authz_epoch']+1
  checks.append(dict(name='REVOKED_ACTUAL_NATIVE_SOURCE_NO_FAVORABLE_REUSE',actual=verdict,receipt=receipt))
  conn.sendall((json.dumps(dict(jsonrpc='2.0',id=4,method='tools/call',params=dict(name='build_evidence_bundle',arguments=dict(query_id=q['query_id'],experience_id=exp,view='recommendation'))))+'\n').encode())
  try:
   stale=stream.readline();assert not stale or json.loads(stale).get('result',{}).get('isError') is True
   observed='CLOSED' if not stale else 'EXPLICIT_ERROR'
  except ConnectionResetError:observed='CONNECTION_RESET'
  checks.append(dict(name='ACTUAL_OFFICIAL_MCP_STALE_CACHED_RECOMMENDATION_REFUSED',actual=observed))
  try:h._check();raise AssertionError('Stale Host capability retained')
  except V2Error as err:assert err.code=='UNAUTHORIZED';checks.append(dict(name='OLD_HOST_GRANT_REFUSED',actual=err.code))
 finally:stream.close();conn.close()
mp.undo();assert b.metadata['handler_cleanup_complete']

snap('after-revocation');write(O/'RESULT.json',{'status':'PASS','classification':'HOST_CONTROLLED_GRAPH_TEST','source_native_run':pub['run_id'],'source_publication_sha256':sha(E/'04_live'/selected['label']/'HOST_PUBLICATION.json'),'graph':name,'port':kw['port'],'checks':checks,'actual_model_decision':'SEPARATELY_IN_ORIGINAL_NATIVE_TRACE_NOT_THESE_TESTS','same_domain_conflict_and_poisoning':'fresh inherited real DB tests and new native protocol/authority tests; explicit evidence matrix links required'})
r.close();print('REAL_NATIVE_SOURCE_CONTROLLED_GRAPH_PASS')
