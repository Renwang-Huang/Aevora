"""Host-only publication of the actual reviewed S1 candidate; no task steering."""
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
out=E/'04_live/S1/publication';out.mkdir();r=GraphRepository.from_environment();raw=RawCommands(out);raw.attach(r);life=CandidateLifecycle(r)
try:
 review=json.loads((E/'04_live/S1/HOST_SEMANTIC_REVIEW.json').read_text());source=json.loads((E/'04_live/S1/host_source/0/source_verification.json').read_text());cid=review['candidate_id'];view=life.inspect(cid)
 assert review['semantic_review']=='BOUNDED_PLAUSIBLE_FROM_ACTUAL_PATCH' and review['host_decision']=='APPROVE_BOUNDED_PUBLICATION'
 assert review['body_sha256']==view['candidate']['body_sha256'] and review['submission_sha256']==source['source']['submission_sha256'] and source['outcome_verdict']=='PASS'
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'graph_before.json',before)
 grant=ReviewGrant('v5c1-trusted-host-reviewer',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).isoformat())
 life.transition(cid,'ADMITTED_BOUNDED',expected_head_sha256=view['head_sha256'],event_key='v5c1-admit',reason='Actual native lease-authority repair passes independent36-case Oracle in the declared public factual scope; no causal guarantee',grant=grant,metadata={'source_id':source['source']['id'],'scope':view['candidate']['body']['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'})
 pub=life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='v5c1-publish',reason='Approve original Agent proposal after independent native source, patch, scope and Oracle verification; preserve all limitations',grant=grant)
 write(out/'PUBLICATION.json',pub);write(out/'FINAL_CANDIDATE.json',life.inspect(cid));after=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'graph_after.json',after)
 scopes={}
 for ep in ['A','D','D-V02']:
  facts=public_runtime_context(json.loads((E/'owned_runtime/source/benchmark/scenarios'/ep/'public.json').read_text()));result=ExperienceResolver(r).resolve(facts,persist_snapshots=False);write(out/('HOST_SCOPE_CHECK_'+ep+'.json'),result);scopes[ep]={v['experience_id']:v['decision'] for v in result['candidates']}
 write(E/'04_live/PUBLISHED_EXPERIENCE.json',{'at':now(),'candidate_id':cid,'new_published_experience_id':pub['experience_id'],'native_source_run_id':source['source']['run_id'],'body_sha256':view['candidate']['body_sha256'],'source_verification_id':source['source']['id'],'publication':pub,'host_scope_decisions':scopes,'s2_episode':'D-V02','s2_selection_rule':'FIXED_BY_PRE_REGISTRATION_NOT_PUBLICATION_RESULT','not_delivered_to_participant_as_hint':True,'causal_benefit':'UNKNOWN'})
 r._client.connection.save();write(out/'RESULT.json',{'status':'PASS','at':now(),'publication':pub,'original_candidate_body_unchanged':life.inspect(cid)['candidate']['body_sha256']==review['body_sha256'],'old_competitors_retained':r.experience_ids(),'source_review_sha256':sha(E/'04_live/S1/HOST_SEMANTIC_REVIEW.json'),'scope_decisions':scopes,'causal_benefit':'UNKNOWN'});print('ACTUAL_BOUNDED_PUBLICATION',pub['experience_id'],scopes['D-V02'][pub['experience_id']],flush=True)
finally:raw.close();r.close()
