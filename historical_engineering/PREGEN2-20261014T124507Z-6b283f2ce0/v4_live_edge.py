from pathlib import Path
import sys,json
E=Path(__file__).resolve().parent;sys.path[:0]=[str(E),str(E/'owned_runtime/source')]
from audit import write,now
from aevora.graph_repository import GraphRepository
from aevora.experience_resolver import ExperienceResolver
from aevora.historical_import import ATOMIC_ID,public_context
r=GraphRepository.from_environment();out=E/'05_product/live_browser_ablation';out.mkdir(mode=0o700,exist_ok=True)
try:
 context=public_context('multi_process_shared_sqlite');before=ExperienceResolver(r).resolve(context,persist_snapshots=False)
 if sys.argv[1]=='cut':
  c=next(x for x in before['candidates'] if x['experience_id']==ATOMIC_ID);path=c['principle_support_paths'][0];s=path['records']['Evidence']['id'];t=path['records']['VerifiedOutcome']['id'];edge=r.query('MATCH(s:Evidence {id:$s})-[r:VERIFIES]->(t:VerifiedOutcome {id:$t}) RETURN r.id,r.payload_json',{'s':s,'t':t});assert len(edge)==1
  write(out/'EDGE.json',{'source':s,'target':t,'edge':edge[0],'before':before,'at':now()});r.query('MATCH(s:Evidence {id:$s})-[r:VERIFIES {id:$id}]->(t:VerifiedOutcome {id:$t}) DELETE r',{'s':s,'t':t,'id':edge[0][0]},read_only=False)
  actual=ExperienceResolver(r).resolve(context,persist_snapshots=False);assert next(x for x in actual['candidates'] if x['experience_id']==ATOMIC_ID)['decision']=='VERIFY';write(out/'CUT.json',actual)
 elif sys.argv[1]=='restore':
  e=json.loads((out/'EDGE.json').read_text());r.put_edge('VERIFIES','Evidence',e['source'],'VerifiedOutcome',e['target'],json.loads(e['edge'][1]));actual=ExperienceResolver(r).resolve(context,persist_snapshots=False);assert next(x for x in actual['candidates'] if x['experience_id']==ATOMIC_ID)['decision']=='APPLY';write(out/'RESTORED.json',actual)
 else:raise ValueError('Unknown bounded operation')
finally:r.close()
