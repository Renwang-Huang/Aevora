"""Explicitly untrusted observation lookup; never an applicability engine."""
from .candidate import validate_proposal, CandidateLifecycle


def search(repository, query, limit=10):
    if not isinstance(query,str) or len(query.encode())>1000 or len(query.split())>8 or type(limit) is not int or not 1<=limit<=20:
        raise ValueError('Bounded literal observation search required')
    rows=repository.query('MATCH (c:Candidate) RETURN c.id ORDER BY c.id LIMIT $take',{'take':501})
    observations=[]
    for row in rows[:500]:
        candidate=repository.get_node('Candidate',row[0]);body=validate_proposal(candidate['body'])
        text=' '.join(body[k] for k in ('title','public_summary','strategy')).lower()
        if query.split() and not any(term.lower() in text for term in query.split()):continue
        view=CandidateLifecycle(repository).inspect(candidate['id'])
        public={k:body[k] for k in ('title','public_summary','strategy','necessary_conditions','inapplicable_conditions','scope','unknown_fields','limitations','derived_from_candidate_id') if k in body}
        observations.append({**public,'candidate_id':candidate['id'],'run_id':candidate['run_id'],'body_sha256':candidate['body_sha256'],
                             'state':view['head']['state'],'authority':'UNTRUSTED_OBSERVATION','applicability':'NOT_EVALUATED','_created':candidate['created_at']})
    observations.sort(key=lambda row:(row['_created'],row['candidate_id']),reverse=True)
    for row in observations:row.pop('_created')
    return {'status':'PARTIAL' if len(rows)>500 else 'AVAILABLE','query':query,'observations':observations[:limit],
            'authority':'UNTRUSTED_OBSERVATIONS_ONLY','applicability':'NOT_EVALUATED','adoption':'UNKNOWN','causal_benefit':'UNKNOWN',
            'limit':limit,'ordering':'RECENT_MATCHES; literal public narrative keywords; not semantic confidence',
            'assurance':'Investigative leads only; no APPLY or verified outcome. Python reference scans at most 500 candidates.'}
