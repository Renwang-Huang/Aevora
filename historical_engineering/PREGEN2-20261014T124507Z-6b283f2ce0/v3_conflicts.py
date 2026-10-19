from pathlib import Path
import sys,os,json,threading,datetime,uuid
from concurrent.futures import ThreadPoolExecutor
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle,ReviewGrant
from aevora.models import ImmutableConflict,LIFECYCLE_SCHEMA_VERSION
from aevora.historical_import import ATOMIC_ID,public_context
from aevora.experience_resolver import ExperienceResolver
from aevora.checkpoint import capture_graph
from scripts.aevora_h2_graph_e2e import RawCommands
from aevora.orderflow_outcome_bridge import TrustAnchor,verify_outcome,OutcomeVerificationError,M1_MANIFEST_SHA256
out=E/'04_falkordb/head_revision_conflicts-attempt2';out.mkdir(mode=0o700)
os.environ['AEVORA_FALKORDB_GRAPH']=json.loads((E/'04_falkordb/graph_controls-attempt3/RESULT.json').read_text())['graph']
r=GraphRepository.from_environment();raw=RawCommands(out);lock=threading.Lock();oldappend=raw.append
def append(x):
 with lock:oldappend(x)
raw.append=append;raw.attach(r);life=CandidateLifecycle(r)
try:
 p={'candidate_key':'head-conflict','title':'Explicit Host concurrent head control','strategy':'No strategy is published by this unverified control','public_summary':'Concurrency and authority negative control; no Agent or Oracle outcome asserted.','necessary_conditions':{'shared_state_kind':['sqlite_file']},'inapplicable_conditions':{},'scope':{'shared_state_kind':['sqlite_file']},'unknown_fields':[],'limitations':['Unverified; excluded from resolver'],'source_references':[]}
 cid=life.propose('pregen2-head-control-'+uuid.uuid4().hex,p)['candidate_id'];h=life.inspect(cid)['head_sha256'];barrier=threading.Barrier(2)
 g=ReviewGrant('pregen2-host',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=15)).isoformat())
 def call(i):
  barrier.wait()
  try:life.transition(cid,'EVIDENCE_PENDING',expected_head_sha256=h,event_key='contender'+str(i),reason='Actual concurrent Host head control',grant=g);return 'won'
  except ImmutableConflict:return 'stale'
 with ThreadPoolExecutor(max_workers=2) as pool:res=list(pool.map(call,[0,1]))
 assert sorted(res)==['stale','won'];write(out/'CONCURRENT_HEAD.json',{'status':'PASS','actual':res,'view':life.inspect(cid)})
 before=capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION);write(out/'REVISION_BEFORE.json',before)
 original=[x['record'] for x in r.governance_view(ATOMIC_ID)['revisions']]
 predecessors=[x['id'] for x in original if x.get('revision_kind')!='rule_publication']
 if len(predecessors)!=1:predecessors=[x['id'] for x in original]
 assert len(predecessors)==1
 for i in [1,2]:
  rule={'id':'rule:pregen2-concurrent-control:'+str(i),'version':'pregen2-host-control','premises':[{'id':'premise:pregen2-sqlite:'+str(i),'fact_key':'shared_state_kind','allowed_values':['sqlite_file'],'required':True}]}
  r.append_rule_revision(ATOMIC_ID,rule,revision_id='revision:pregen2-conflict:'+str(i),supersedes_ids=predecessors,source_type='maintainer_seed',scope={'concurrency_scope':['independent_processes']},valid_from=now(),public_reason='Explicit Host conflicting revisions; does not assert a new engineering result')
 actual=ExperienceResolver(r).resolve(public_context('multi_process_shared_sqlite'),persist_snapshots=False);selected=next(x for x in actual['candidates'] if x['experience_id']==ATOMIC_ID);assert selected['decision']=='VERIFY'
 write(out/'CONFLICTING_REVISIONS.json',{'status':'PASS','resolution':actual,'after':capture_graph(r,schema_version=LIFECYCLE_SCHEMA_VERSION),'scope':'Real Host conflict control; no fabricated VerifiedOutcome'})
 hist=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/orderflow_incident_lab/m1_validation');a=Path((hist/'CURRENT').read_text().strip());a=a if a.is_absolute() else hist/a
 anchor=TrustAnchor(a,M1_MANIFEST_SHA256,{'offline-final/runs/cf083714-0a91-4392-81ed-1070f2cdef71/evaluation_report.json':'cf083714-0a91-4392-81ed-1070f2cdef71'})
 count=r.query('MATCH(n:VerifiedOutcome) RETURN count(n)')
 try:verify_outcome(anchor,'invented-run/evaluation_report.json')
 except OutcomeVerificationError as e:write(out/'FAKE_ORACLE_RUN_REJECTED.json',{'status':'PASS','error_type':type(e).__name__,'outcome_count_before':count,'outcome_count_after':r.query('MATCH(n:VerifiedOutcome) RETURN count(n)')})
 else:raise ValueError('Fake run accepted')
 assert count==r.query('MATCH(n:VerifiedOutcome) RETURN count(n)')
 r._client.connection.save();write(out/'RESULT.json',{'status':'PASS','checks':3,'scope':'Actual2Host contenders; actualconflictingrulepublications; actualfalseOracleallowlistrejection','at':now()})
 print('V3 conflicts PASS')
finally:raw.close();r.close()
