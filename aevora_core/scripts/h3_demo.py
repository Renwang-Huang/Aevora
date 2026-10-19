"""H3-demo: read-only JSON observation over an actual live FalkorDB graph.

Run with independently installed aevora-core and Host-only DB credentials.
No Benchmark imports, fixed recommendation, replayed Outcome or model request.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from datetime import datetime,timezone


EXTRA_FIELDS={
 'Candidate':('id','run_id','body','body_sha256','source_type','created_at','schema_version'),
 'LifecycleHead':('id','candidate_id','state','sequence','event_id'),
 'CandidateEvent':('id','candidate_id','from_state','to_state','sequence','previous_event_id','event_key','reason','authority','principal','metadata','created_at'),
 'SourceVerification':('id','candidate_id','run_id','origin','authority','source_sha256','submission_sha256','outcome_id','facts','native_thread_id','source_epoch','causal_benefit','proposal_event_references'),
 'ExternalObservation':('id','run_id','status','authority','source_sha256','public_summary','created_at','trusted_outcome','attribution'),
 'Query':('id','run_id','task_context','candidate_experience_ids','query_snapshot_ids','created_at','decision_engine_version'),
 'Decision':('id','run_id','query_id','experience_id','decision','reason','verification_steps','authority','adoption','attribution','created_at','query_snapshot_id'),
 'QuerySnapshot':('id','content_sha256','created_at'),
 'ObservedAction':('id','run_id','submission_digest','source_type','authority','attribution'),
 'Feedback':('id','experience_id','outcome_id','attribution','feedback_status','source_type'),
 'AuditEvent':('id','event_type','candidate_id','record_id','authority','public_reason','created_at')}


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')


def main():
    from aevora.graph_repository import GraphRepository
    from aevora.models import public_record
    from aevora.candidate import CandidateLifecycle
    from aevora.experience_resolver import ExperienceResolver
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--candidate',required=True);p.add_argument('--external-run',required=True)
    a=p.parse_args();a.output.mkdir(parents=True,mode=0o700)
    repo=GraphRepository.from_environment()
    try:
        native=CandidateLifecycle(repo).inspect(a.candidate)
        source_id=next(e['metadata']['source_id'] for e in native['events'] if e['to_state']=='ADMITTED_BOUNDED')
        facts=repo.get_node('SourceVerification',source_id)['facts']
        contexts={'bounded_source':facts,'independent_workers':{**facts,'concurrency_scope':'independent_processes','synchronization_scope':'process_local'}}
        views={k:ExperienceResolver(repo).resolve(v,persist_snapshots=False) for k,v in contexts.items()}
        write(a.output/'WHEN_WHY.json',views)
        write(a.output/'CANDIDATE_LIFECYCLE.json',native)
        external=repo.query('MATCH(n:ExternalObservation {run_id:$run}) RETURN n.payload_json',{'run':a.external_run})
        if len(external)!=1:raise ValueError('Actual external observation absent or ambiguous')
        observation=json.loads(external[0][0]);write(a.output/'EXTERNAL_OBSERVATION.json',observation)
        outcome_count=repo.query('MATCH(n:VerifiedOutcome {run_id:$run}) RETURN count(n)',{'run':a.external_run})
        if outcome_count!=[[0]]:raise ValueError('External project unexpectedly has a VerifiedOutcome')
        nodes=[]
        for labels,identity,raw,source_sha in repo.query('MATCH(n) RETURN labels(n),n.id,n.payload_json,n.payload_sha256 ORDER BY n.id'):
            if len(labels)!=1:raise ValueError('Ambiguous graph label')
            label=labels[0];payload=json.loads(raw)
            projected=({k:payload[k] for k in EXTRA_FIELDS[label] if k in payload} if label in EXTRA_FIELDS else public_record(label,payload))
            nodes.append({'label':label,'id':identity,'public':projected,'stored_payload_sha256':source_sha})
        edges=[{'source':s,'relation':r,'id':i,'stored_payload_sha256':h,'target':t} for s,r,i,h,t in
               repo.query('MATCH(s)-[r]->(t) RETURN s.id,type(r),r.id,r.payload_sha256,t.id ORDER BY s.id,type(r),r.id,t.id')]
        write(a.output/'PUBLIC_GRAPH.json',{'graph':repo.graph_name,'nodes':nodes,'edges':edges,
            'projection':'Explicit public allowlists; stored payload hashes refer to full trusted graph records, not the projected bytes.'})
        write(a.output/'TIMELINE.json',{'candidate_events':native['events'],'external':observation,
            'public_query_decisions':[n['public'] for n in nodes if n['label'] in ('Query','Decision')],
            'event_source':'Actual graph records; unavailable timestamps remain absent, never inferred.'})
        files={q.name:sha256(q.read_bytes()).hexdigest() for q in sorted(a.output.iterdir()) if q.is_file()}
        write(a.output/'MANIFEST.json',{'kind':'AEVORA_H3_READ_ONLY_DEMO','schema_version':'1.0','files':files,
            'candidate_id':a.candidate,'external_run_id':a.external_run,'graph':repo.graph_name,'database_port':int(__import__('os').environ['AEVORA_FALKORDB_PORT']),
            'observed_at':datetime.now(timezone.utc).isoformat(),'model_calls':0,'source_script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
            'causal_benefit':'UNKNOWN','trust':'Local read-only observation; not external attestation or an atomic graph snapshot.'})
        print(json.dumps({'status':'PASS','files':len(files),'model_calls':0,'external_verified_outcomes':0}));return 0
    finally:repo.close()


if __name__=='__main__':raise SystemExit(main())
