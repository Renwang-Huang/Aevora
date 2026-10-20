from pathlib import Path
import json,hashlib,collections
E=Path(__file__).parent;out=[]
for p in sorted((E/'06_regression/acceptance-host-58/artifacts/graphs').glob('*.json')):
 v=json.loads(p.read_text());states=[];events=[];heads=[];outcomes=[];manifests=[]
 for labels,props in v['nodes']:
  n=json.loads(props['payload_json'])
  if n['kind']=='TenantState':states.append(n)
  if n['kind']=='CandidateEvent':events.append({k:n.get(k) for k in ['id','candidate_id','state','event_type','sequence','previous_event']})
  if n['kind']=='LifecycleHead':heads.append({k:n.get(k) for k in ['id','candidate_id','state','event_id','sequence']})
  if n['kind']=='VerifiedOutcome':outcomes.append({k:n.get(k) for k in ['id','independent_run_id','verdict','artifact_sha256','result_sha256']})
  if n['kind']=='PublicationManifest':manifests.append({k:n.get(k) for k in ['id','epoch','experience_id','document']})
 out.append(dict(graph=p.stem,snapshot_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),graph_state_sha256=v['sha256'],initial='Fresh fixture initialized at epoch0/authz0/empty discovery; exact creation and all changes in per-process raw streams',final_states=states,events=events,heads=heads,outcomes=outcomes,manifests=manifests,nodes=len(v['nodes']),edges=len(v['edges'])))
(E/'reports/G22_GRAPH_DIFFS.json').write_text(json.dumps(dict(source='Actual final snapshots + immutable event chains; original raw Cypher in same acceptance root',graphs=out),sort_keys=True,indent=2))
print(len(out),'graph state/event diffs indexed')
