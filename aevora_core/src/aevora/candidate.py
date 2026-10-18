"""Untrusted proposals and a trusted, append-only FalkorDB admission ledger.

One write query fences each state change and appends its event/relationships.
Experience construction remains retryable multi-query work behind PUBLISHING;
the resolver excludes it until the final fenced publication. This is not causal
attribution, global experience ranking, or an Agent orchestrator.
"""
from dataclasses import dataclass
import re
from .models import (InvalidRecord, GraphError, ImmutableConflict, GraphUnavailable,
    canonical_json, digest, validate_id, validate_scope, normalize_context,
    parse_timestamp, utc_now, PUBLIC_CONTEXT_FACTS, LIFECYCLE_SCHEMA_VERSION)
from .governance import scope_relation, fact_state, equal

VERSION = 'aevora.candidate/1.0'
STATES = {'PROPOSED', 'EVIDENCE_PENDING', 'REJECTED', 'ADMITTED_BOUNDED',
          'PUBLISHING', 'PUBLISHED', 'WITHDRAWN', 'SUPERSEDED'}
TRANSITIONS = {'PROPOSED': {'EVIDENCE_PENDING', 'REJECTED'},
    'EVIDENCE_PENDING': {'REJECTED', 'ADMITTED_BOUNDED'},
    'ADMITTED_BOUNDED': {'PUBLISHING', 'WITHDRAWN'},
    'PUBLISHING': {'PUBLISHED', 'WITHDRAWN'},
    'PUBLISHED': {'WITHDRAWN', 'SUPERSEDED'}}
_SENSITIVE = re.compile(r'(?i)(sk-[a-z0-9-]{16,}|/home/|/maintainer/|/proc/|hidden_tests|private_manifests|private_labels|reference_patches|(?:ignore|override) (?:all |previous |system )?instructions|system prompt)')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


def public_text(value, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        raise InvalidRecord('Bounded public text required')
    if _SENSITIVE.search(value):
        raise InvalidRecord('Sensitive path, credential or instruction payload rejected')
    return value


def validate_proposal(value):
    allowed = {'candidate_key', 'title', 'strategy', 'public_summary', 'necessary_conditions',
               'inapplicable_conditions', 'scope', 'unknown_fields', 'limitations', 'source_references'}
    if not isinstance(value, dict) or set(value) != allowed:
        raise InvalidRecord('Proposal requires documented fields only; authority fields forbidden')
    validate_id(value['candidate_key'])
    if len(value['candidate_key']) > 64 or ':' in value['candidate_key'] or '/' in value['candidate_key']:
        raise InvalidRecord('Short local candidate key required')
    for key in ('title', 'strategy', 'public_summary'): public_text(value[key])
    for key in ('necessary_conditions', 'inapplicable_conditions', 'scope'):
        validate_scope(value[key])
    if not value['necessary_conditions'] or not value['scope']:
        raise InvalidRecord('Explicit necessary conditions and bounded scope required')
    for key in ('unknown_fields', 'limitations'):
        rows = value[key]
        if not isinstance(rows, list) or len(rows) > 32: raise InvalidRecord('Bounded text list required')
        for row in rows: public_text(row, 1000)
    if set(value['unknown_fields']) - PUBLIC_CONTEXT_FACTS:
        raise InvalidRecord('Unknown fields must use public semantic facts')
    refs = value['source_references']
    if not isinstance(refs, list) or len(refs) > 32: raise InvalidRecord('Bounded source references required')
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'kind', 'id'} or ref['kind'] not in {'Query', 'Decision', 'ObservedAction'}:
            raise InvalidRecord('References are graph identities, never arbitrary paths or outcomes')
        validate_id(ref['id'])
    if len(canonical_json(value).encode()) > 16384: raise InvalidRecord('Proposal exceeds16KiB')
    return __import__('json').loads(canonical_json(value))


def validate_lifecycle_record(label, payload):
    if label == 'Candidate':
        validate_proposal(payload.get('body'))
        if payload.get('body_sha256') != digest(payload['body']) or payload.get('authority') != 'UNTRUSTED_PROPOSAL':
            raise InvalidRecord('Candidate body/authority mismatch')
        validate_id(payload.get('run_id')); parse_timestamp(payload.get('created_at'))
        if payload.get('provenance') != 'UNVERIFIED_UNTIL_HOST_REVIEW': raise InvalidRecord('Proposal cannot establish origin')
    elif label == 'LifecycleHead':
        validate_id(payload.get('candidate_id')); validate_id(payload.get('event_id'))
        if payload.get('state') not in STATES or type(payload.get('sequence')) is not int or payload['sequence'] < 0:
            raise InvalidRecord('Invalid lifecycle head')
    elif label == 'CandidateEvent':
        validate_id(payload.get('candidate_id'))
        if payload.get('to_state') not in STATES or type(payload.get('sequence')) is not int:
            raise InvalidRecord('Invalid candidate event')
        parse_timestamp(payload.get('created_at'))
    elif label == 'SourceVerification':
        if payload.get('authority') != 'TRUSTED_HOST_SOURCE_VERIFIER' or payload.get('origin') not in {
                'natural_agent_run', 'maintainer_seed', 'synthetic_or_test_fixture', 'external_unverified'}:
            raise InvalidRecord('Source authority required')
        validate_id(payload.get('run_id')); normalize_context(payload.get('facts', {}))
        for key in ('source_sha256', 'submission_sha256'):
            if not isinstance(payload.get(key), str) or not _SHA.fullmatch(payload[key]): raise InvalidRecord('Actual source digest required')
        if payload.get('origin') == 'natural_agent_run' and not payload.get('outcome_id'):
            raise InvalidRecord('Natural bounded admission requires independently verified outcome')
    elif label == 'ExternalObservation':
        if payload.get('authority') != 'EXTERNAL_UNVERIFIED' or payload.get('trusted_outcome') != 'NOT_CREATED':
            raise InvalidRecord('External observation cannot be verified')
        validate_id(payload.get('run_id')); public_text(payload.get('public_summary'))
        if not isinstance(payload.get('source_sha256'), str) or not _SHA.fullmatch(payload['source_sha256']):
            raise InvalidRecord('Actual external observation source digest required')


@dataclass(frozen=True)
class ReviewGrant:
    """Host-only, short-lived review authority; never accepted by public tools.

    The trusted operating-system caller owns DB credentials. This is not a
    signature service or protection against a compromised graph administrator.
    """
    principal: str
    expires_at: str

    def check(self):
        validate_id(self.principal)
        remaining=(parse_timestamp(self.expires_at)-parse_timestamp(utc_now())).total_seconds()
        if remaining <= 0:
            raise InvalidRecord('Review authorization expired')
        if remaining>3600:raise InvalidRecord('Review authorization exceeds one-hour host lease')


def _edge(kind, sl, sid, tl, tid):
    value = {'id': 'edge:' + digest([kind, sl, sid, tl, tid])}
    return {'id': value['id'], 'payload': canonical_json(value), 'sha': digest(value)}


class CandidateLifecycle:
    def __init__(self, repository): self.repo = repository

    def initialize(self):
        return self.repo.initialize(schema_version=LIFECYCLE_SCHEMA_VERSION)

    def propose(self, run_id, proposal):
        schema = self.repo.get_node('Schema', LIFECYCLE_SCHEMA_VERSION)
        if not schema or schema.get('version') != LIFECYCLE_SCHEMA_VERSION:
            raise GraphError('Trusted lifecycle schema initialization required before proposal')
        validate_id(run_id); body = validate_proposal(proposal)
        identifier = 'candidate:' + run_id + ':' + body['candidate_key']; validate_id(identifier)
        for ref in body['source_references']:
            record = self.repo.get_node(ref['kind'], ref['id'])
            if not record or record.get('run_id') != run_id:
                raise InvalidRecord('Source reference is absent or belongs to another run')
        old = self.repo.get_node('Candidate', identifier)
        candidate = {'id': identifier, 'run_id': run_id, 'body': body, 'body_sha256': digest(body),
            'created_at': old['created_at'] if old else utc_now(), 'schema_version': VERSION,
            'authority': 'UNTRUSTED_PROPOSAL', 'provenance': 'UNVERIFIED_UNTIL_HOST_REVIEW',
            'agent_thread_id': 'UNAVAILABLE'}
        self.repo.put_node('Candidate', candidate)
        event_id = 'candidate-event:' + digest(identifier) + ':proposed'
        event = {'id': event_id, 'candidate_id': identifier, 'from_state': None, 'to_state': 'PROPOSED',
            'previous_event_id': None, 'sequence': 0, 'created_at': candidate['created_at'],
            'request_sha256': digest(candidate), 'reason': 'Untrusted run-bound proposal',
            'authority': 'UNTRUSTED_PROPOSAL', 'metadata': {}}
        self.repo.put_node('CandidateEvent', event)
        head_id = 'candidate-head:' + digest(identifier)
        head = {'id': head_id, 'candidate_id': identifier, 'event_id': event_id, 'sequence': 0, 'state': 'PROPOSED'}
        try:
            if not self.repo.get_node('LifecycleHead', head_id):
                self.repo.put_node('LifecycleHead', head)
        except (ImmutableConflict, GraphUnavailable):
            if not self.repo.get_node('LifecycleHead', head_id): raise
        self.repo.put_edge('HAS_LIFECYCLE', 'Candidate', identifier, 'LifecycleHead', head_id)
        self.repo.put_edge('HAS_CANDIDATE_EVENT', 'Candidate', identifier, 'CandidateEvent', event_id)
        return {'status': 'PROPOSED_UNTRUSTED', 'candidate_id': identifier, 'body_sha256': digest(body),
            'run_id': run_id, 'publication': 'NOT_PUBLISHED', 'source_type': 'UNVERIFIED', 'schema_version': VERSION}

    def inspect(self, identifier):
        validate_id(identifier)
        candidate = self.repo.get_node('Candidate', identifier)
        head = self.repo.get_node('LifecycleHead', 'candidate-head:' + digest(identifier))
        if not candidate or not head: raise InvalidRecord('Candidate lifecycle absent or incomplete')
        self.repo.require_edge('HAS_LIFECYCLE', 'Candidate', identifier, 'LifecycleHead', head['id'])
        chain = []; current = head['event_id']; expected = head['sequence']
        while current:
            if len(chain) >= 128: raise GraphError('Lifecycle chain bound exceeded')
            event = self.repo.get_node('CandidateEvent', current)
            if not event or event.get('candidate_id') != identifier or event.get('sequence') != expected:
                raise GraphError('Lifecycle event chain corrupt')
            self.repo.require_edge('HAS_CANDIDATE_EVENT', 'Candidate', identifier, 'CandidateEvent', current)
            if event['previous_event_id']:
                self.repo.require_edge('PREVIOUS_EVENT', 'CandidateEvent', current, 'CandidateEvent', event['previous_event_id'])
            elif expected != 0 or event['to_state'] != 'PROPOSED':
                raise GraphError('Lifecycle genesis corrupt')
            chain.append(event); current = event['previous_event_id']; expected -= 1
        if expected != -1 or chain[0]['to_state'] != head['state']:
            raise GraphError('Lifecycle head mismatch')
        for newer, older in zip(chain, chain[1:]):
            if newer['from_state'] != older['to_state'] or newer['to_state'] not in TRANSITIONS.get(older['to_state'], set()):
                raise GraphError('Invalid recorded transition')
        return {'candidate': candidate, 'head': head, 'head_sha256': digest(head), 'events': list(reversed(chain)),
                'consistency': 'Actual multi-query observation; immutable event chain; not atomic read snapshot'}

    def transition(self, identifier, state, *, expected_head_sha256, event_key, reason, grant, metadata=None):
        if not isinstance(grant, ReviewGrant): raise InvalidRecord('Trusted host review grant required')
        grant.check(); public_text(reason); validate_id(event_key)
        if len(event_key) > 64 or ':' in event_key or '/' in event_key: raise InvalidRecord('Local event key required')
        if not _SHA.fullmatch(expected_head_sha256 or ''): raise InvalidRecord('Expected head digest required')
        metadata = metadata or {}
        if set(metadata) - {'source_id', 'scope', 'strength', 'experience_id', 'superseded_by'}:
            raise InvalidRecord('Unsupported transition metadata')
        if 'scope' in metadata: validate_scope(metadata['scope'])
        if 'strength' in metadata and metadata['strength'] != 'BOUNDED_SUPPORT_NOT_CAUSAL':
            raise InvalidRecord('Causal/universal claims not admitted')
        event_id = 'candidate-event:' + digest(identifier) + ':' + event_key
        request = {'candidate_id': identifier, 'state': state, 'expected_head_sha256': expected_head_sha256,
                   'reason': reason, 'principal': grant.principal, 'expires_at': grant.expires_at, 'metadata': metadata}
        existing = self.repo.get_node('CandidateEvent', event_id)
        if existing:
            if existing['request_sha256'] != digest(request):
                self.repo._audit_conflict(label='CandidateEvent', record_id=event_id,
                                         expected=existing['request_sha256'], received=digest(request))
                raise ImmutableConflict('Event ID reused with a different review request')
            return {'event': existing, 'idempotent_replay': True, 'state_at_event': existing['to_state']}
        view = self.inspect(identifier); head = view['head']
        if digest(head) != expected_head_sha256 or state not in TRANSITIONS.get(head['state'], set()):
            self.repo.put_node('AuditEvent', {'id': 'candidate-rejected-transition:' + digest(request),
                'event': 'stale_or_illegal_candidate_transition', 'candidate_id': identifier,
                'request_sha256': digest(request), 'actual_head_sha256': digest(head)})
            raise ImmutableConflict('Stale or illegal lifecycle transition')
        if state == 'ADMITTED_BOUNDED': self._admission(view['candidate'], metadata)
        if state in {'PUBLISHING', 'PUBLISHED'}:
            admissions = [e for e in view['events'] if e['to_state'] == 'ADMITTED_BOUNDED']
            if len(admissions) != 1: raise InvalidRecord('Unique bounded admission required')
            self._admission(view['candidate'], admissions[0]['metadata'])
        event = {'id': event_id, 'candidate_id': identifier, 'from_state': head['state'], 'to_state': state,
                 'previous_event_id': head['event_id'], 'sequence': head['sequence'] + 1,
                 'created_at': utc_now(), 'request_sha256': digest(request), 'reason': reason,
                 'authority': 'TRUSTED_HOST_REVIEW', 'principal': grant.principal, 'metadata': metadata}
        new_head = {**head, 'state': state, 'sequence': event['sequence'], 'event_id': event_id}
        candidate_edge = _edge('HAS_CANDIDATE_EVENT', 'Candidate', identifier, 'CandidateEvent', event_id)
        previous_edge = _edge('PREVIOUS_EVENT', 'CandidateEvent', event_id, 'CandidateEvent', head['event_id'])
        params = {'candidate': identifier, 'head': head['id'], 'expected': expected_head_sha256,
            'event': event_id, 'event_json': canonical_json(event), 'event_sha': digest(event),
            'previous': head['event_id'], 'head_json': canonical_json(new_head), 'head_sha': digest(new_head),
            **{'ce_' + k: v for k,v in candidate_edge.items()}, **{'pe_' + k:v for k,v in previous_edge.items()}}
        rows = self.repo.query('MATCH (c:Candidate {id:$candidate}),(h:LifecycleHead {id:$head}),'
            '(p:CandidateEvent {id:$previous}) WHERE h.payload_sha256=$expected '
            'CREATE (e:CandidateEvent {id:$event,payload_json:$event_json,payload_sha256:$event_sha}) '
            'CREATE (c)-[:HAS_CANDIDATE_EVENT {id:$ce_id,payload_json:$ce_payload,payload_sha256:$ce_sha}]->(e) '
            'CREATE (e)-[:PREVIOUS_EVENT {id:$pe_id,payload_json:$pe_payload,payload_sha256:$pe_sha}]->(p) '
            'SET h.payload_json=$head_json,h.payload_sha256=$head_sha RETURN e.payload_sha256', params, read_only=False)
        if rows != [[digest(event)]]:
            self.repo.put_node('AuditEvent', {'id': 'candidate-concurrent-conflict:' + digest(request),
                'event': 'concurrent_candidate_head_conflict', 'candidate_id': identifier,
                'request_sha256': digest(request), 'expected_head_sha256': expected_head_sha256})
            raise ImmutableConflict('Concurrent review lost the atomic head fence')
        return {'event': event, 'idempotent_replay': False, 'state_at_event': state}

    def _admission(self, candidate, metadata):
        source = self.repo.get_node('SourceVerification', validate_id(metadata.get('source_id')))
        if not source or source['run_id'] != candidate['run_id'] or source['origin'] == 'external_unverified':
            raise InvalidRecord('Independent same-run verified source required')
        if metadata.get('strength') != 'BOUNDED_SUPPORT_NOT_CAUSAL': raise InvalidRecord('Bounded evidence strength required')
        body = candidate['body']; facts = source['facts']
        required=set(body['necessary_conditions'])|set(body['scope'])|set(metadata.get('scope',{}))
        if required & set(body['unknown_fields']):
            raise InvalidRecord('Declared unknown required premises remain pending')
        for scope in (body['necessary_conditions'], body['scope'], metadata.get('scope', {})):
            if not scope or scope_relation(facts, scope)[0] != 'MATCH': raise InvalidRecord('Unproved or contradictory admission scope')
        # Reviewer may restrict the proposal, never broaden its declared scope.
        reviewed = metadata['scope']
        for key, values in body['scope'].items():
            if key not in reviewed or any(not any(equal(v,x) for x in values) for v in reviewed[key]):
                raise InvalidRecord('Review cannot broaden the proposed scope')
        if body['inapplicable_conditions'] and scope_relation(facts, body['inapplicable_conditions'])[0] != 'UNRELATED':
            raise InvalidRecord('Known/potential inapplicable conditions block admission')
        outcome = self.repo.get_node('VerifiedOutcome', source.get('outcome_id', 'absent'))
        if not outcome or outcome['verdict'] != 'PASS' or outcome['run_id'] != source['run_id']:
            raise InvalidRecord('An independently verified PASS source is required for bounded support')
        self.repo.require_edge('HAS_SOURCE_VERIFICATION', 'Candidate', candidate['id'], 'SourceVerification', source['id'])
        return source

    def publish(self, identifier, *, expected_head_sha256, event_key, reason, grant):
        grant.check(); view = self.inspect(identifier)
        eid = 'experience:published:' + digest(identifier)
        if view['head']['state'] == 'ADMITTED_BOUNDED':
            self.transition(identifier, 'PUBLISHING', expected_head_sha256=expected_head_sha256,
                event_key=event_key + '-begin', reason=reason, grant=grant, metadata={'experience_id': eid})
            view = self.inspect(identifier)
        elif view['head']['state'] == 'PUBLISHED':
            self.publication_allowed(identifier, eid)
            return {'status': 'PUBLISHED', 'experience_id': eid, 'candidate_id': identifier, 'idempotent_replay': True}
        elif view['head']['state'] != 'PUBLISHING' or view['head_sha256'] != expected_head_sha256:
            raise ImmutableConflict('Publication requires current admitted/staged head')
        candidate = view['candidate']; admission = next(e for e in view['events'] if e['to_state'] == 'ADMITTED_BOUNDED')
        source = self._admission(candidate, admission['metadata']); body = candidate['body']
        origin = source['origin']; created = view['events'][-1]['created_at']; rid = eid + '/revision/initial'
        experience = {'id': eid, 'strategy': body['strategy'], 'title': body['title'], 'public_summary': body['public_summary'],
            'source_type': origin, 'created_at': created, 'limitations': body['limitations'] + ['Bounded support, causal benefit UNKNOWN'],
            'origin_run_id': source['run_id'], 'origin_patch_sha256': source['submission_sha256'], 'publication_candidate_id': identifier}
        conditions = dict(body['necessary_conditions'])
        for key, values in admission['metadata']['scope'].items():
            if key in conditions:
                values = [v for v in values if any(equal(v,x) for x in conditions[key])]
                if not values: raise InvalidRecord('Review scope contradicts necessary conditions')
            conditions[key] = values
        rule = {'id': 'rule:' + digest(identifier), 'version': VERSION, 'public_description': 'Host-reviewed factual conditions',
            'premises': [{'id': 'premise:' + digest([identifier,key]), 'fact_key': key, 'allowed_values': values,
                          'required': True} for key,values in sorted(conditions.items())]}
        self.repo.import_experience(experience, rule, rid)
        evidence = {'id': 'evidence:candidate:' + digest(identifier), 'source_type': origin,
            'public_summary': 'Host verified a submitted engineering artifact in the declared factual scope; attribution UNKNOWN.',
            'source_run_id': source['run_id'], 'created_at': created, 'attribution': 'UNKNOWN'}
        context = {'id': 'context:candidate:' + digest(identifier), 'facts': source['facts'], 'source_type': origin}
        task = {'id': 'task:candidate:' + digest(identifier), 'public_title': 'Independently evaluated source submission'}
        rows = self.repo.query('MATCH(o:VerifiedOutcome {id:$id})-[:IN_CONTEXT]->(c:Context)-[:FOR_TASK]->(t:Task) '
                              'RETURN c.payload_json,t.payload_json', {'id': source['outcome_id']})
        if rows:
            if len(rows) != 1: raise GraphError('Ambiguous source outcome environment')
            import json
            context, task = (json.loads(p) for p in rows[0])
            if context.get('facts') != source['facts']: raise InvalidRecord('Verified environment cannot be reinterpreted')
        self.repo.attach_evidence(eid, evidence, self.repo.get_node('VerifiedOutcome', source['outcome_id']), context, task, revision_id=rid)
        self.repo.put_edge('PUBLISHED_FROM', 'Experience', eid, 'Candidate', identifier)
        self.transition(identifier, 'PUBLISHED', expected_head_sha256=view['head_sha256'], event_key=event_key + '-complete',
                        reason=reason, grant=grant, metadata={'experience_id': eid})
        return {'status': 'PUBLISHED', 'experience_id': eid, 'candidate_id': identifier, 'causal_benefit': 'UNKNOWN'}

    def publication_allowed(self, identifier, experience_id):
        view = self.inspect(identifier)
        if view['head']['state'] != 'PUBLISHED': return False
        last = view['events'][-1]
        if last['metadata'].get('experience_id') != experience_id: raise GraphError('Publication identity mismatch')
        self.repo.require_edge('PUBLISHED_FROM', 'Experience', experience_id, 'Candidate', identifier)
        return True
