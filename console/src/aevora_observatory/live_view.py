"""Compose independently paged public LIVE resources, without whole-graph reads."""
from aevora.candidate import CandidateLifecycle, lifecycle_next_steps, candidate_checklist
from aevora.models import QUERY_VERSION, digest
from ._public_projection import project, decision_view
from .live_graph import BoundedRepository, LivePages, encode_cursor, MAX_NODES, MAX_EDGES, MAX_PAYLOAD_BYTES

RUN_LABELS = ['Query', 'Candidate', 'Decision', 'VerifiedOutcome']
PENDING = {'PROPOSED', 'EVIDENCE_PENDING', 'ADMITTED_BOUNDED', 'PUBLISHING'}


def sessions(pages, runtime):
    repo = pages.repo
    after = pages.after.get('sessions', '')
    runtime = {s['run_id']: s for s in runtime}
    ids = [r[0] for r in repo.query('MATCH (n) WHERE (' + ' OR '.join('n:' + label for label in RUN_LABELS)
        + ') AND n.run_id>$after RETURN DISTINCT n.run_id AS identity ORDER BY identity LIMIT $take',
        {'after': after, 'take': pages.offset + pages.limit + 1})]
    merged = sorted(set(ids) | {rid for rid in runtime if rid > after})
    more = len(merged) > pages.offset + pages.limit
    ids = merged[pages.offset:pages.offset + pages.limit]
    pages.pagination['sessions'] = {'limit': pages.limit, 'offset': pages.offset, 'has_more': more,
        'next_cursor': encode_cursor({**pages.after, 'sessions': ids[-1]}, pages.run, pages.experience) if more else None,
        'order': 'identity ASC'}
    # A deep-linked selection remains visible even on another selector page.
    if pages.run and pages.run not in ids:
        ids.append(pages.run)
    counts = repo.query('MATCH (n) WHERE n.run_id IN $runs RETURN n.run_id,labels(n),count(n) '
                        'ORDER BY n.run_id LIMIT $take', {'runs': ids, 'take': (pages.limit + 1) * 32}) if ids else []
    grouped = {}
    for rid, labels, count in counts:
        if len(labels) == 1 and labels[0] in RUN_LABELS:
            grouped.setdefault(rid, {})[labels[0]] = count
    result = []
    for rid in ids:
        if rid not in grouped and rid not in runtime:
            continue
        row = {'run_id': rid, 'session_id': None, 'status': 'RECORDS_OBSERVED',
               'source': 'ACTUAL_CORE_RECORDS', 'authority': 'RECORDS_ONLY; runtime identity unavailable',
               'process_liveness': 'UNAVAILABLE_NOT_PROBED', **runtime.get(rid, {})}
        row.update(query_count=grouped.get(rid, {}).get('Query', 0),
                   candidate_count=grouped.get(rid, {}).get('Candidate', 0),
                   decision_count=grouped.get(rid, {}).get('Decision', 0))
        result.append(row)
    return result


def overview(repository, *, observed_at, runtime, resource='overview', run=None,
             experience=None, limit=20, offset=0, after=None):
    repo = BoundedRepository(repository)
    pages = LivePages(repo, run=run, experience=experience, limit=limit, offset=offset, after=after)
    all_resources = resource == 'overview'
    wants = lambda name: all_resources or resource == name
    result = {'mode': 'LIVE', 'visibility': 'PUBLIC', 'observed_at': observed_at, 'captured_at': None,
              'archive': None, 'contract_sha256': None, 'status': 'AVAILABLE'}
    runtime_rows = runtime() if wants('sessions') else []
    session_rows = sessions(pages, runtime_rows) if wants('sessions') else []
    selected_record = repo.get_node('Experience', experience) if experience and wants('experiences') else None
    experiences = []
    if wants('experiences'):
        if experience:
            experiences = [project('Experience', selected_record)] if selected_record else []
            pages.pagination['experiences'] = {'limit': 1, 'has_more': False, 'next_cursor': None,
                                                'order': 'selected identity'}
        else:
            experiences = pages.public('experiences', ['Experience'])
    available = []
    for value in experiences:
        candidate = value.get('publication_candidate_id')
        if not candidate or CandidateLifecycle(repo).publication_allowed(candidate, value['id']):
            available.append(value['id'])
    candidates = pages.public('candidates', ['Candidate'], run_scoped=True) if all_resources else []
    heads = []
    for candidate in candidates:
        head = repo.get_node('LifecycleHead', 'candidate-head:' + digest(candidate['id']))
        if head is None or head['candidate_id'] != candidate['id']:
            raise ValueError('Candidate head mismatch')
        repo.require_edge('HAS_LIFECYCLE', 'Candidate', candidate['id'], 'LifecycleHead', head['id'])
        heads.append(project('LifecycleHead', head))
    query_match = 'MATCH (n)-[:CONSIDERED]->(:Experience {id:$experience})' if experience else 'MATCH (n)'
    queries = pages.public('queries', ['Query'], run_scoped=True, match=query_match) if wants('decisions') else []
    decisions = []
    for query in queries:
        full = repo.get_node('Query', query['id'])
        if experience and experience not in query.get('query_snapshot_ids', {}):
            raise ValueError('Considered experience has no recorded snapshot')
        for eid, snapshot_id in query.get('query_snapshot_ids', {}).items():
            if experience is not None and eid != experience:
                continue
            repo.require_edge('CONSIDERED', 'Query', query['id'], 'Experience', eid)
            repo.require_query_snapshot_edge(query['id'], snapshot_id)
            content = repo.load_query_snapshot(snapshot_id)
            if content.get('candidate', {}).get('experience_id') != eid or content.get('context') != full.get('task_context'):
                raise ValueError('Stored query snapshot association mismatch')
            decisions.append({**decision_view(content['candidate'], query['id'], snapshot_id),
                              'run_id': query['run_id'], 'created_at': query.get('created_at'),
                              'authority': 'RECORDED_CORE_QUERY_SNAPSHOT', 'as_of': content.get('as_of')})
    if wants('decisions'):
        pages.pagination['decisions'] = {**pages.pagination['queries'], 'unit': 'Query headers; all selected snapshots per Query'}
    decision_match = 'MATCH (n)-[:DECIDED]->(:Experience {id:$experience})' if experience else 'MATCH (n)'
    recorded = pages.public('recorded_decisions', ['Decision'], run_scoped=True, match=decision_match) if all_resources else []
    if experience is not None:
        if any(d['experience_id'] != experience for d in recorded):
            raise ValueError('Decision experience association mismatch')
    timeline = []
    if wants('timeline'):
        match = 'MATCH (n)'
        predicates = []
        if run:
            # Older CandidateEvent/AuditEvent records have candidate_id only
            # inside canonical JSON, without a materialized run property.
            # Match that exact field in DB; do not load all candidate bodies.
            match += (' OPTIONAL MATCH (c:Candidate {run_id:$run}) '
                      'WHERE n.payload_json CONTAINS (\'"candidate_id":"\' + c.id + \'"\') WITH n,c')
            predicates.append('(n.run_id=$run OR c.run_id=$run)')
        timeline = pages.public('timeline', ['CandidateEvent', 'GovernanceEvent', 'AuditEvent', 'Decision', 'Query'],
                                where=predicates, match=match)
        if run:
            for row in timeline:
                if row.get('run_id') == run:
                    continue
                candidate = repo.get_node('Candidate', row.get('candidate_id'))
                if not candidate or candidate.get('run_id') != run:
                    raise ValueError('Timeline candidate association mismatch')
    trusted = pages.public('trusted', ['VerifiedOutcome'], run_scoped=True) if wants('outcomes') else []
    external = pages.public('external', ['ExternalObservation'], run_scoped=True) if wants('outcomes') else []
    graph = pages.graph() if wants('graph') else None
    lifecycle = None
    if selected_record and selected_record.get('publication_candidate_id'):
        full = CandidateLifecycle(repo).inspect(selected_record['publication_candidate_id'])
        lifecycle = {'candidate': project('Candidate', full['candidate']), 'head': project('LifecycleHead', full['head']),
                     'events': [project('CandidateEvent', e) for e in full['events']]}
    health = {'database': 'AVAILABLE', 'mcp': 'UNAVAILABLE_NOT_ACTIVE_PROBED', 'live_fallback': False}
    if resource == 'health':
        health['recent_core_query_records'] = repo.query('MATCH (n:Query) RETURN count(n)')[0][0]
    if all_resources:
        totals = {labels[0]: count for labels, count in repo.query('MATCH (n) RETURN labels(n),count(n) LIMIT 32')
                  if len(labels) == 1}
        total_runs = repo.query('MATCH (n) WHERE ' + ' OR '.join('n:' + label for label in RUN_LABELS)
                                + ' RETURN count(DISTINCT n.run_id)')[0][0]
        runtime_ids = {s['run_id'] for s in runtime_rows}
        if runtime_ids:
            overlap = repo.query('MATCH (n) WHERE (' + ' OR '.join('n:' + label for label in RUN_LABELS)
                                + ') AND n.run_id IN $runs RETURN count(DISTINCT n.run_id)',
                                {'runs': sorted(runtime_ids)})[0][0]
            total_runs += len(runtime_ids) - overlap
        # Exact availability requires Core chain validation. Never scan every
        # experience/head just to fill a metric; disclose incomplete totals.
        summary_heads = LivePages(repo, limit=limit).records('candidates', ['LifecycleHead'])
        summary_heads = {v['id']: project(label, v) for label, v in summary_heads}
        summary_heads.update({h['id']: h for h in heads})
        complete_heads = len(summary_heads) == totals.get('LifecycleHead', 0)
        summary_experiences = experiences
        summary_available = len(available)
        if experience:
            # Project readiness is independent of a selected or missing record.
            # Validate a bounded first page without substituting it into the view.
            summary_experiences = LivePages(repo, limit=limit).public('experiences', ['Experience'])
            summary_available = sum(not v.get('publication_candidate_id') or
                CandidateLifecycle(repo).publication_allowed(v['publication_candidate_id'], v['id'])
                for v in summary_experiences)
        complete_experiences = len(summary_experiences) == totals.get('Experience', 0)
        pending = sum(h['state'] in PENDING for h in summary_heads.values())
        meaningful = repo.query('MATCH (n) WHERE NOT n:Schema RETURN count(n)')[0][0]
        state = ('EXPERIENCE_AVAILABLE' if summary_available else 'CANDIDATES_PENDING' if pending else
                 'ACTIVITY_RECORDED' if totals.get('Query') or session_rows else 'RECORDS_PRESENT' if meaningful else 'EMPTY')
        summary = {
            'EXPERIENCE_AVAILABLE': 'Published experiences are available. Use a new task query to check applicability.',
            'CANDIDATES_PENDING': 'Candidates are recorded and await Host verification, review or publication.',
            'ACTIVITY_RECORDED': 'Task activity is recorded.',
            'RECORDS_PRESENT': 'The project contains records.',
            'EMPTY': 'Database connected. This project has no records yet; connect MCP and start a task.',
        }
        counts = {'records': meaningful, 'runs': total_runs, 'queries': totals.get('Query', 0),
                  'candidates': totals.get('Candidate', 0), 'stored_experiences': totals.get('Experience', 0),
                  'pending_candidates': pending if complete_heads else None,
                  'available_experiences': summary_available if complete_experiences else None}
        result.update(project={'graph': repo.graph_name, 'state': state, 'summary': summary[state], 'counts': counts,
                      'count_scope': 'Project aggregates; null means not fully validated in this bounded read',
                      'loaded_counts': {'pending_candidates': pending, 'available_experiences': summary_available},
                      'candidate_states': {s: sum(h['state'] == s for h in summary_heads.values())
                                           for s in sorted({h['state'] for h in summary_heads.values()})},
                      'candidate_states_complete': complete_heads},
                      selection={'run_id': run, 'run_status': 'ALL' if run is None else 'AVAILABLE'
                                 if any(s['run_id'] == run for s in session_rows) else 'NOT_FOUND',
                                 'experience_id': experience, 'experience_status': 'ALL' if experience is None
                                 else 'AVAILABLE' if selected_record else 'NOT_FOUND'},
                      case=None, sessions=session_rows, experiences=experiences, available_experience_ids=sorted(available),
                      candidates=candidates, candidate_heads=heads,
                      candidate_guidance={h['candidate_id']: {**lifecycle_next_steps(h['state']),
                          'checklist': candidate_checklist(next(c for c in candidates if c['id']==h['candidate_id']), h['state'])}
                          for h in heads},
                      lifecycle=lifecycle, graph=graph, decisions=decisions, activity_queries=queries,
                      recorded_decisions=recorded, timeline=timeline,
                      outcomes={'trusted': trusted, 'external': external,
                                'authority_policy': 'Only graph VerifiedOutcome records are trusted; external observations remain unverified'},
                      health={**health, 'recent_core_query_records': totals.get('Query', 0)},
                      live_query_context=None, context_authority='RECORDED_QUERY_SNAPSHOTS_ONLY; no synthetic task context',
                      comparison=None, evolution=None,
                      sources={'core': 'Core publication gate and immutable QuerySnapshot records; no resolver execution',
                               'graph': repo.graph_name, 'query_version': QUERY_VERSION},
                      causal_benefit='UNKNOWN', agent_adoption='UNKNOWN',
                      consistency='Actual multi-query observation, not atomic snapshot',
                      ordering='Pages ordered by stable identity; timestamps do not establish cross-stream causality')
        result['status'] = 'EMPTY' if state == 'EMPTY' else 'AVAILABLE'
    else:
        values = {'sessions': session_rows, 'experiences': experiences, 'decisions': decisions, 'timeline': timeline,
                  'graph': graph, 'outcomes': {'trusted': trusted, 'external': external}, 'health': health}
        result.update(resource=resource, data=values[resource], limit=limit, offset=offset)
    result['pagination'] = pages.pagination
    result['read_budget'] = {'nodes': len(repo.nodes), 'edges': repo.read_edges, 'payload_bytes': repo.payload_bytes,
                             'queries': repo.read_queries, 'max_nodes': MAX_NODES, 'max_edges': MAX_EDGES,
                             'max_payload_bytes': MAX_PAYLOAD_BYTES, 'max_response_bytes': MAX_PAYLOAD_BYTES}
    return result
