"""Host-only bounded review and real publication; selection is not Agent retrieval."""
from pathlib import Path
import sys,json,datetime
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,sha,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.checkpoint import capture_graph
from aevora.models import LIFECYCLE_SCHEMA_VERSION
from aevora.experience_resolver import ExperienceResolver
from integrations.aevora import public_runtime_context
from scripts.aevora_h2_graph_e2e import RawCommands
out=E/'03_feedback/publication';out.mkdir();r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);life=CandidateLifecycle(r)
try:
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'graph_before.json',before)
 a=json.loads((E/'03_feedback/HOST_SEMANTIC_REVIEW.json').read_text());cid=a['candidate_id'];view=life.inspect(cid)
 s=json.loads((E/'03_feedback/source/0/source_verification.json').read_text())
 assert a['body_sha256']==view['candidate']['body_sha256'] and a['submission_sha256']==s['source']['submission_sha256']
 assert a['semantic_review']=='BOUNDED_PLAUSIBLE_FROM_ACTUAL_PATCH' and s['outcome_verdict']=='PASS'
 grant=ReviewGrant('v5c-trusted-host-reviewer',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).isoformat())
 life.transition(cid,'ADMITTED_BOUNDED',expected_head_sha256=view['head_sha256'],event_key='v5c-admit',reason='One independently passed native repair supports the declared factual scope; no universal or causal guarantee',grant=grant,metadata={'source_id':s['source']['id'],'scope':view['candidate']['body']['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'})
 pub=life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='v5c-publish',reason='Approve bounded same-run engineering evidence and preserve declared unknowns and limitations',grant=grant)
 write(out/'PUBLICATION.json',pub);write(out/'FINAL_CANDIDATE.json',life.inspect(cid))
 after=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'graph_after.json',after)
 def delta(key):
  old={json.dumps(x,sort_keys=True) for x in before[key]};new={json.dumps(x,sort_keys=True) for x in after[key]}
  return {'added':[json.loads(x) for x in sorted(new-old)],'removed':[json.loads(x) for x in sorted(old-new)]}
 write(out/'graph_delta.json',{'nodes':delta('nodes'),'edges':delta('edges'),'before':before['graph_sha256'],'after':after['graph_sha256'],'scope':'ACTUAL_QUIESCENT_OWNED_GRAPH; not an atomic global transaction'})
 selection={}
 for ep in ['A','D']:
  manifest=json.loads((E/'owned_runtime/source/benchmark/scenarios'/ep/'public.json').read_text());context=public_runtime_context(manifest)
  result=ExperienceResolver(r).resolve(context,persist_snapshots=False);write(out/('HOST_SCOPE_CHECK_'+ep+'.json'),result)
  selection[ep]=next(x['decision'] for x in result['candidates'] if x['experience_id']==pub['experience_id'])
 episode='A' if selection['A']=='APPLY' else 'D'
 write(E/'03_feedback/S2_SELECTION.json',{'episode':episode,'new_published_experience_id':pub['experience_id'],'candidate_id':cid,'public_scope_check':selection,'preregistered_rule':'Prefer A only if actual Core APPLY; otherwise fresh D-v01','same_template_fallback':episode=='D','not_agent_retrieval':True,'not_delivered_to_participant':True,'no_s1_patch_context_or_grade_injection':True,'at':now()})
 r._client.connection.save();write(out/'RESULT.json',{'status':'PASS','publication':pub,'s2_episode':episode,'candidate_origin':'natural_agent_run','causal_benefit':'UNKNOWN','at':now()})
 print('REAL_PUBLICATION',pub['experience_id'],episode,selection)
finally:raw.close();r.close()
