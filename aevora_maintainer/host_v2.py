"""OS-authorized Host admission and Graph v2 publication (not a public MCP API).

The caller must own the private registry and independent archive trust anchors.
An Agent proposal is data. It is never a verifier, grant or a Prepared object.
All visibility changes are performed by one parameterized GRAPH.QUERY fence.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import os
import copy
import json
from aevora.contracts import *
from aevora.models import utc_now
from aevora.governance import equal
from aevora.graph_queries import SEMANTIC_RELATIONS
from aevora.graph_v2 import validate_witness
from aevora.host_pins import PinMap, read_registry
from aevora.orderflow_outcome_bridge import TrustAnchor, verify_outcome, _Archive, _manifest

TRANSITIONS = {'PROPOSED': {'EVIDENCE_PENDING', 'REJECTED'},
               'EVIDENCE_PENDING': {'ADMITTED_BOUNDED', 'REJECTED'},
               'ADMITTED_BOUNDED': {'PUBLISHING', 'WITHDRAWN'},
               'PUBLISHING': {'PUBLISHED', 'WITHDRAWN'},
               'PUBLISHED': {'WITHDRAWN', 'SUPERSEDED'},
               'WITHDRAWN': set(), 'SUPERSEDED': set(), 'REJECTED': set()}


def narrowed(child, parent):
    scope(child); scope(parent)
    return all(k in child and all(any(equal(v, p) for p in vs) for v in child[k])
               for k, vs in parent.items())


class HostPins:
    """Durable, no-overwrite trust allowlist; graph activation is separate."""
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = PinMap(self.root, 'authorities')._open_root(); os.close(fd)

    def put(self, category, key, value):
        require(category in {'authorities', 'outcomes', 'fact_sources', 'publications', 'candidates', 'sources', 'reviews', 'preparations'})
        raw = canonical_json(dict(category=category, key=key, value=value)).encode()
        require(len(raw) <= 4096, 'CAPACITY_EXCEEDED')
        mapping = PinMap(self.root, category)
        fd = mapping._open_root()
        try:
            name = digest([category, key]) + '.json'
            try:
                f = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=fd)
            except FileExistsError:
                require(mapping[key] == value, 'IMMUTABLE_CONFLICT')
                return
            try:
                require(os.write(f, raw) == len(raw)); os.fsync(f)
            finally:
                os.close(f)
            os.fsync(fd)
        finally:
            os.close(fd)


@dataclass(frozen=True)
class HostGrant:
    tenant: str
    principal: str
    capability_id: str
    generation: str
    authz_epoch: int
    valid_until: str
    profile: str = PROFILE

    def __post_init__(self):
        for value in [self.tenant,self.principal,self.capability_id,self.generation]:validate_id(value)
        require(type(self.authz_epoch) is int and self.authz_epoch>=0 and self.profile==PROFILE,'UNAUTHORIZED')
        timestamp(self.valid_until)


@dataclass(frozen=True)
class Verifier:
    """Only the maintainer supplies anchors, evaluator and suite allowlists."""
    authority_id: str
    anchor: TrustAnchor
    evaluator_sha: str
    suite_sha: str

    def __post_init__(self):
        validate_id(self.authority_id);require(isinstance(self.anchor,TrustAnchor),'UNAUTHORIZED')
        require(all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in [self.evaluator_sha,self.suite_sha]))


@dataclass(frozen=True)
class Prepared:
    """Only an identifier; every byte is reloaded from immutable graph staging."""
    identifier: str
    sha256: str

    def __post_init__(self):
        validate_id(self.identifier);require(isinstance(self.sha256,str) and re.fullmatch('[0-9a-f]{64}',self.sha256))


class TrustedHost:
    def __init__(self, repo, pin_root, grant, verifiers=()):
        self.repo, self.grant = repo, grant
        self.pins = HostPins(pin_root)
        self.repo.registry = read_registry(pin_root)
        self.verifiers = {v.authority_id: v for v in verifiers}
        self._check()

    @staticmethod
    def bootstrap(repo, pin_root, *, principal, allowed_scope, ttl_seconds=1800,
                  generation='1'):
        """Trusted deployment action, excluded from product/Participant imports."""
        require(0 < ttl_seconds <= 3600, 'UNAUTHORIZED'); scope(allowed_scope)
        state = repo.state()
        until = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        cap = record(repo.tenant, 'Authority', ['host-capability', principal, generation],
                     authority_class='TRUSTED_HOST', independence='HOST', state='ACTIVE',
                     verifier_version='aevora.host/2.0', source_sha256=digest(['host', principal]),
                     principal=principal, scope=allowed_scope, grant_generation=generation,
                     profile=PROFILE, valid_until=until, visibility='HOST_ONLY')
        repo.put_node(cap)
        return HostGrant(repo.tenant, principal, cap['id'], generation,
                         state['authz_epoch'], until)

    def _check(self, requested_scope=None):
        g = self.grant; s = self.repo.state(); cap = self.repo.node(g.capability_id)
        require(g.tenant == self.repo.tenant and g.profile == PROFILE
                and type(g.authz_epoch) is int and g.authz_epoch == s['authz_epoch']
                and cap['state'] == 'ACTIVE' and cap['principal'] == g.principal
                and cap['grant_generation'] == g.generation and cap['profile'] == g.profile
                and cap['valid_until'] == g.valid_until
                and timestamp(g.valid_until) > datetime.now(timezone.utc), 'UNAUTHORIZED')
        if requested_scope is not None:
            require(narrowed(requested_scope, cap['scope']), 'UNAUTHORIZED')
        return s, cap

    def _immutable(self, value):
        if self.repo.execute('Q13', id=value['id']):
            old=self.repo.node(value['id'])
            require({k:v for k,v in old.items() if k!='created_at'} ==
                    {k:v for k,v in value.items() if k!='created_at'}, 'IMMUTABLE_CONFLICT')
            return old
        self.repo.put_node(value)
        return value

    def register_orderflow(self, anchor, evaluator_sha, suite_sha):
        _,issuer_cap=self._check()
        # Pins come from the Host deployment, never from a Candidate's report.
        require(isinstance(anchor, TrustAnchor), 'UNAUTHORIZED')
        for value in (evaluator_sha, suite_sha):
            require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value))
        a = record(self.repo.tenant, 'Authority', ['orderflow-verifier', evaluator_sha, suite_sha, anchor.manifest_sha256, self.grant.principal, self.grant.generation],
                   authority_class='INDEPENDENT_ORACLE', independence='INDEPENDENT',
                   state='ACTIVE', verifier_version='AevoraOrderFlowOutcomeBridge/0.2.0',
                   valid_from=utc_now(), valid_until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                   source_sha256=evaluator_sha, suite_sha256=suite_sha,source_anchor_manifest_sha256=anchor.manifest_sha256,scope=issuer_cap['scope'])
        # Identical verifier registration is idempotent, including created_at.
        rows = self.repo.execute('Q13', id=a['id'])
        if rows:
            a = self.repo.node(a['id'])
            require(a['source_sha256'] == evaluator_sha and a['suite_sha256'] == suite_sha)
        else:
            self.repo.put_node(a)
        self.pins.put('authorities', a['id'], digest(a))
        v = Verifier(a['id'], anchor, evaluator_sha, suite_sha)
        self.verifiers[v.authority_id] = v
        return v

    def propose(self, proposal, *, run_id, tree_sha, patch_sha=None, origin='HOST_SEEDED', native_candidate_id=None):
        validate_schema('propose_experience.arguments', {'proposal': proposal})
        self._check(proposal['scope'])
        from aevora.candidate import public_text
        for k in ['title','strategy','public_summary']:public_text(proposal[k])
        require(origin in {'HOST_SEEDED', 'AGENT_PROPOSED'}, 'INVALID_INPUT')
        require(origin != 'AGENT_PROPOSED' or native_candidate_id is not None, 'SOURCE_MISMATCH')
        key = ['candidate', run_id, proposal['candidate_key']]
        identifier = identity(self.repo.tenant, 'Candidate', key)
        rows = self.repo.execute('Q13', id=identifier)
        if rows:
            old = self.repo.node(identifier)
            require(old['body_sha256'] == digest(proposal) and old['tree_sha256'] == tree_sha
                    and old['patch_sha256'] == patch_sha and old['origin'] == origin
                    and old.get('native_candidate_id') == native_candidate_id,
                    'IMMUTABLE_CONFLICT')
            return old
        c = record(self.repo.tenant, 'Candidate', key, body=copy.deepcopy(proposal),
                   body_sha256=digest(proposal), run_id=run_id, tree_sha256=tree_sha,
                   patch_sha256=patch_sha, origin=origin, native_candidate_id=native_candidate_id, state='PROPOSED_UNTRUSTED',
                   visibility='HOST_ONLY')
        self.repo.put_node(c)
        self.pins.put('candidates',c['id'],digest(c))
        event = record(self.repo.tenant, 'CandidateEvent', [c['id'], 'PROPOSED'],
                       candidate_id=c['id'], state='PROPOSED', sequence=0,
                       reason='Immutable untrusted proposal received', visibility='HOST_ONLY')
        head = record(self.repo.tenant, 'LifecycleHead', c['id'], candidate_id=c['id'],
                      event_id=event['id'], state='PROPOSED', sequence=0, visibility='HOST_ONLY')
        self.repo.put_node(event); self.repo.put_node(head)
        self.repo.put_edge(edge(self.repo.tenant, 'HAS_LIFECYCLE', c, head))
        self.repo.put_edge(edge(self.repo.tenant, 'HAS_CANDIDATE_EVENT', c, event))
        return c

    def head(self, candidate):
        return self.repo.node(identity(self.repo.tenant, 'LifecycleHead', candidate))

    def transition(self, candidate, target, *, expected_head, reason):
        self._check(); head = self.head(candidate)
        require(digest(head) == expected_head, 'CONFLICT')
        require(target in TRANSITIONS[head['state']] and target != 'PUBLISHED'
                and head['state'] != 'PUBLISHED', 'INVALID_TRANSITION')
        ev = record(self.repo.tenant, 'CandidateEvent', [candidate, target, expected_head],
                    candidate_id=candidate, state=target, sequence=head['sequence'] + 1,
                    previous_event=head['event_id'], reason=reason, visibility='HOST_ONLY')
        new = {**head, 'state': target, 'sequence': ev['sequence'], 'event_id': ev['id']}
        # All lifecycle events are immutable and associated with previous head.
        self.repo.put_node(ev)
        c = self.repo.node(candidate); prev = self.repo.node(head['event_id'])
        self.repo.put_edge(edge(self.repo.tenant, 'HAS_CANDIDATE_EVENT', c, ev))
        self.repo.put_edge(edge(self.repo.tenant, 'PREVIOUS_EVENT', ev, prev))
        rows = self.repo.transport.query(
            'MATCH(h:LifecycleHead {id:$id}),(cap:Authority {id:$cap}),(s:TenantState {id:$state}) '
            'WHERE h.payload_sha256=$old AND cap.state=\'ACTIVE\' AND s.authz_epoch=$authz '
            'SET h=$new RETURN h.payload_sha256',
            dict(id=head['id'], cap=self.grant.capability_id, state=self.repo.state_id,
                 old=expected_head, authz=self.grant.authz_epoch, new=native(new)), read_only=False)
        require(rows == [[digest(new)]], 'CONFLICT')
        return new

    def _verified(self, candidate, authority_id, report_reference):
        self._check(); require(authority_id in self.verifiers, 'UNAUTHORIZED')
        v = self.verifiers[authority_id]; a = self.repo.node(authority_id)
        s = self.repo.state()
        require(authority_id not in s.get('revoked_authorities', []) and a['state'] == 'ACTIVE'
                and timestamp(a['valid_from']) <= datetime.now(timezone.utc) < timestamp(a['valid_until']), 'UNAUTHORIZED')
        require(self.repo.registry.authorities.get(a['id']) == digest(a), 'UNAUTHORIZED')
        outcome = verify_outcome(v.anchor, report_reference)
        c = self.repo.node(candidate)
        require(PinMap(self.pins.root,'candidates').get(c['id'])==digest(c)
                and c['body_sha256']==digest(c['body']), 'SOURCE_MISMATCH')
        validate_schema('propose_experience.arguments',{'proposal':c['body']})
        require(outcome['run_id'] == c['run_id'] and outcome['candidate_tree_sha256'] == c['tree_sha256']
                and outcome['patch_sha256'] == c['patch_sha256']
                and outcome['evaluator_fingerprint'] == v.evaluator_sha
                and outcome['test_suite_fingerprint'] == v.suite_sha, 'SOURCE_MISMATCH')
        return c, a, outcome

    def verify_source(self, candidate, authority_id, report_reference):
        c, a, out = self._verified(candidate, authority_id, report_reference)
        head = self.head(candidate)
        if head['state'] == 'PROPOSED':
            self.transition(candidate, 'EVIDENCE_PENDING', expected_head=digest(head), reason='Host source verification started')
        require(self.head(candidate)['state'] == 'EVIDENCE_PENDING', 'INVALID_TRANSITION')
        native_refs = 'UNAVAILABLE'
        if c['origin'] == 'AGENT_PROPOSED':
            # This path requires actual typed source evidence; never accept a
            # supplied thread string or an approximate timestamp association.
            from aevora_maintainer.native_source import verify_native_v2
            native_refs = verify_native_v2(self.verifiers[authority_id].anchor,
                                           out, c['native_candidate_id'], c['body_sha256'],
                                           expected_tenant=self.repo.tenant)
        source = record(self.repo.tenant, 'SourceVerification', ['source', candidate, authority_id, digest(out)],
                        candidate_id=candidate, body_sha256=c['body_sha256'], origin=c['origin'],
                        run_id=c['run_id'], artifact_sha256=c['tree_sha256'], patch_sha256=c['patch_sha256'],
                        source_manifest_sha256=out['source_manifest_sha256'],
                        native_source=native_refs, verification='SOURCE_VERIFIED',
                        outcome_authority_id=a['id'], report_reference=str(report_reference),
                        outcome_pin=digest(out), visibility='HOST_ONLY')
        source=self._immutable(source)
        self.pins.put('sources',source['id'],digest(source))
        return source

    def verify_outcome(self, candidate, source_id):
        source = self.repo.node(source_id)
        require(PinMap(self.pins.root,'sources').get(source_id)==digest(source), 'SOURCE_MISMATCH')
        c, authority, out = self._verified(candidate, source['outcome_authority_id'], source['report_reference'])
        require(source['candidate_id'] == candidate and source['body_sha256'] == c['body_sha256']
                and source['outcome_pin'] == digest(out), 'SOURCE_MISMATCH')
        # The verifier already checked real JUnit identities, exit, actual
        # candidate tree, frozen Oracle and every independent DB observation.
        proof = record(self.repo.tenant, 'SourceVerification', ['outcome', source_id],
                       candidate_id=candidate, source_id=source_id, verification='OUTCOME_VERIFIED',
                       verified_outcome=out, visibility='HOST_ONLY')
        proof=self._immutable(proof)
        self.pins.put('sources',proof['id'],digest(proof))
        return proof

    def review(self, candidate, source_id, outcome_id, *, approved_scope, reason):
        self._check(approved_scope); c = self.repo.node(candidate)
        source = self.repo.node(source_id); out = self.repo.node(outcome_id)
        require(PinMap(self.pins.root,'sources').get(source_id)==digest(source)
                and PinMap(self.pins.root,'sources').get(outcome_id)==digest(out), 'SOURCE_MISMATCH')
        _,issuer,_=self._verified(candidate,source['outcome_authority_id'],source['report_reference'])
        require('scope' in issuer and narrowed(approved_scope,issuer['scope']),'UNAUTHORIZED')
        require(source['candidate_id'] == candidate and out['candidate_id'] == candidate
                and out['source_id'] == source_id and out['verification'] == 'OUTCOME_VERIFIED')
        require(narrowed(approved_scope, c['body']['scope']), 'SCOPE_WIDENING')
        # Derive task context exclusively from the independently pinned report.
        from aevora.feedback import _report, _environment
        v = self.verifiers[source['outcome_authority_id']]
        report = _report(v.anchor, source['report_reference'], out['verified_outcome'])
        arc = _Archive(v.anchor.archive_root)
        try:
            report_relative=arc.reference(source['report_reference'])
            raw_report = arc.read(report_relative, 64*1024*1024, out['verified_outcome']['source_report_sha256'])
        finally:
            arc.close()
        first_line_sha = hashlib.sha256(raw_report.splitlines(keepends=True)[0]).hexdigest()
        context, _ = _environment(report, None)
        facts = {}
        for key, value in context['facts'].items():
            fullkey = 'task.' + key
            if fullkey not in schema('fact')['properties']['key']['enum']:
                continue
            known=value is not None and value not in ('unknown','not_observed','not_available')
            f = dict(key=fullkey, phase='task', availability='KNOWN' if known else 'NOT_OBSERVED' if value=='not_observed' else 'UNKNOWN', value=value if known else None,
                     authority_class='HOST_DECLARED_TASK' if known else None, authority_ref=self.grant.capability_id if known else None,
                     observed_at=out['verified_outcome']['evaluated_at'],
                     source_refs=[dict(file=report_relative, file_sha256=out['verified_outcome']['source_report_sha256'],
                                       line=1, line_sha256=first_line_sha,
                                       byte_scope='ARCHIVED_BYTES_INCLUDING_NEWLINE')])
            # Whole report SHA plus exact original first-line bytes. The
            # trusted extractor above obtains facts from the public environment.
            if not known:
                f.update(source_refs=[],observed_at=None)
            fact(f); facts[fullkey] = f
        required = c['body']['necessary_conditions']
        if any(k not in facts or facts[k]['availability'] != 'KNOWN' for k in required):
            return dict(status='PENDING', reason='UNKNOWN_PREMISE', candidate_id=candidate)
        if any(not any(equal(facts[k]['value'], v) for v in values) for k, values in required.items()):
            self.transition(candidate, 'REJECTED', expected_head=digest(self.head(candidate)), reason='PREMISE_CONTRADICTED')
            return dict(status='REJECTED', reason='PREMISE_CONTRADICTED', candidate_id=candidate)
        for k,values in approved_scope.items():
            if k not in facts or facts[k]['availability']!='KNOWN':
                return dict(status='PENDING',reason='UNKNOWN_SCOPE',candidate_id=candidate)
            if not any(equal(facts[k]['value'],v) for v in values):
                self.transition(candidate,'REJECTED',expected_head=digest(self.head(candidate)),reason='SCOPE_NOT_OBSERVED')
                return dict(status='REJECTED',reason='SCOPE_NOT_OBSERVED',candidate_id=candidate)
        proof = record(self.repo.tenant, 'SourceVerification', ['review', candidate, digest(approved_scope), digest(out)],
                       verification='REVIEW_APPROVED', candidate_id=candidate, source_id=source_id,
                       outcome_id=outcome_id, approved_scope=approved_scope, facts=facts,
                       reviewer=self.grant.principal, reason=reason, grant_generation=self.grant.generation,
                       fact_extractor=dict(function='aevora.feedback._environment',source_sha256=hashlib.sha256(Path(__import__('aevora.feedback',fromlist=['_environment']).__file__).read_bytes()).hexdigest(),report_json_pointer='/scenario_metadata/runtime',assurance='HOST_DECLARED_PUBLIC_TASK_NOT_KERNEL_OBSERVATION'),
                       authority_id=source['outcome_authority_id'], visibility='HOST_ONLY')
        proof=self._immutable(proof)
        self.pins.put('reviews',proof['id'],digest(proof))
        for f in facts.values():
            if f['availability']=='KNOWN':self.pins.put('fact_sources',digest(f),f['authority_ref'])
        if self.head(candidate)['state']=='ADMITTED_BOUNDED':
            return proof
        self.transition(candidate, 'ADMITTED_BOUNDED', expected_head=digest(self.head(candidate)), reason=reason)
        return proof

    def prepare(self, candidate, review_id, *, request_key, expected_head, expected_epoch,
                experience_id=None, supersedes=(), governance=None):
        state, cap = self._check(); c = self.repo.node(candidate); h = self.head(candidate)
        review = self.repo.node(review_id)
        require(PinMap(self.pins.root,'reviews').get(review_id)==digest(review), 'UNAUTHORIZED')
        require(review['verification'] == 'REVIEW_APPROVED' and review['candidate_id'] == candidate)
        self._check(review['approved_scope'])
        source = self.repo.node(review['source_id']); op = self.repo.node(review['outcome_id'])
        require(PinMap(self.pins.root,'sources').get(source['id'])==digest(source) and PinMap(self.pins.root,'sources').get(op['id'])==digest(op), 'SOURCE_MISMATCH')
        _, authority, verified = self._verified(candidate, source['outcome_authority_id'], source['report_reference'])
        require(digest(verified) == source['outcome_pin'] and verified == op['verified_outcome'])
        action = 'GOVERN' if governance else 'PUBLISH'
        expected_state = 'PUBLISHED' if governance else 'PUBLISHING'
        semantic = dict(tenant=self.repo.tenant, principal=self.grant.principal, candidate=candidate,
                        action=action, expected_head=expected_head, expected_epoch=expected_epoch,
                        source=digest(source), outcome=digest(op), review=digest(review),
                        scope=review['approved_scope'], reason=review['reason'],
                        experience_id=experience_id, supersedes=list(supersedes), governance=governance)
        request_sha = digest(semantic)
        publication_key = digest([semantic, request_key])
        key = ['publication-request', self.grant.principal, request_key]
        receipt_id = identity(self.repo.tenant, 'SourceVerification', key)
        old_receipt = self.repo.execute('Q13', id=receipt_id)
        if old_receipt:
            old = self.repo.node(receipt_id)
            require(old['request_body_sha256'] == request_sha, 'IMMUTABLE_CONFLICT')
            return Prepared(old['prepared_id'], old['prepared_sha256'])
        require(state['epoch'] == expected_epoch and digest(h) == expected_head, 'CONFLICT')
        require(h['state'] == expected_state, 'INVALID_TRANSITION')
        require(review['reviewer'] == self.grant.principal and review['grant_generation'] == self.grant.generation, 'UNAUTHORIZED')
        prepared_id = identity(self.repo.tenant, 'QuerySnapshot', ['prepared', publication_key])
        if self.repo.execute('Q13', id=prepared_id):
            existing = self.repo.node(prepared_id)
            saved = self.repo.load_document(existing)
            require(PinMap(self.pins.root,'preparations').get(existing['id'])==digest(existing),'UNAUTHORIZED')
            require(saved['request_body_sha256'] == request_sha, 'IMMUTABLE_CONFLICT')
            return Prepared(prepared_id, digest(existing))
        validation_nodes={};validation_edges={};validation_documents={}
        if state['discovery_heads']:
            observed_state,complete_scope=self.repo.resolve_witnesses(review['facts'])
            require(observed_state==state,'CONFLICT')
            for witness in complete_scope:
                validation_nodes.update(witness['nodes']);validation_edges.update(witness['edges'])
                validation_documents[witness['manifest']['id']]=witness['manifest']
                catalogue=self.repo.node(witness['discovery_ref']['catalogue_id'])
                validation_documents[catalogue['id']]=catalogue
        nodes = {}; edges = {}; prior_edges = {}
        token = digest(['task.shared_state_kind', review['approved_scope']['task.shared_state_kind'][0]]) if len(review['approved_scope'].get('task.shared_state_kind', [])) == 1 else '*'
        if experience_id:
            self.repo.discover(review['facts'], state)
            w = self.repo.read_witness(experience_id, state)
            nodes.update(w['nodes']); edges.update(w['edges']); prior_edges.update(w['edges'])
            exp = nodes[experience_id]
            require(exp['scope_token'] == token, 'CROSS_PARTITION_REJECTED')
        else:
            require(not governance and not supersedes, 'INVALID_INPUT')
            exp = record(self.repo.tenant, 'Experience', ['host-experience', candidate],
                         title=c['body']['title'], strategy=c['body']['strategy'], scope_token=token)
            exp=self._immutable(exp)
            nodes[exp['id']] = exp
        def n(kind, name, **body):
            v = record(self.repo.tenant, kind, [publication_key, name], **body)
            nodes[v['id']] = v; return v
        def link(kind, a, b):
            v = edge(self.repo.tenant, kind, a, b); edges[v['id']] = v; return v
        if governance:
            require(set(governance) == {'event_type', 'target_id', 'scope', 'reason'}, 'INVALID_INPUT')
            require(governance['event_type'] in {'withdraw', 'expire', 'restrict_scope'}, 'INVALID_INPUT')
            self._check(governance['scope'])
            target = nodes.get(governance['target_id']); require(target is not None)
            require(target['kind'] in {'ExperienceRevision', 'Evidence'})
            require(narrowed(governance['scope'], review['approved_scope']), 'SCOPE_WIDENING')
            g = n('GovernanceEvent', 'governance', event_type=governance['event_type'],
                  effective_at=utc_now(), scope=governance['scope'], target_id=target['id'],
                  target_label=target['kind'], reason=governance['reason'])
            link('GOVERNS', g, target)
        else:
            reqs = []
            for mode, conditions in [('necessary', c['body']['necessary_conditions']), ('exclusion', c['body']['inapplicable_conditions'])]:
                for k, values in sorted(conditions.items()):
                    reqs.append(n('Premise', [mode, k], fact_key=k, phase=k.split('.')[0], mode=mode, allowed_values=values))
            rule = n('Rule', 'rule', scope_token=token, scope=review['approved_scope'],
                     premise_ids=[p['id'] for p in reqs], strategy_sha256=digest(c['body']['strategy']))
            require(all(i in nodes and nodes[i]['kind'] == 'ExperienceRevision' and nodes[i]['experience_id'] == exp['id'] for i in supersedes), 'CROSS_PARTITION_REJECTED')
            rev = n('ExperienceRevision', 'revision', experience_id=exp['id'],candidate_id=candidate,
                    declared_rule_id=rule['id'], supersedes_ids=list(supersedes),
                    scope=review['approved_scope'], valid_from=utc_now(), revision_kind='rule_publication')
            link('HAS_REVISION', exp, rev); link('USES_RULE', rev, rule)
            for p in reqs: link('REQUIRES', rule, p)
            for i in supersedes: link('SUPERSEDES', rev, nodes[i])
            task = n('Task', 'task', facts=review['facts'])
            ctx = n('Context', 'context', task_id=task['id'], facts=review['facts'])
            outcome = n('VerifiedOutcome', 'outcome', authority=authority['id'],
                        task_id=task['id'], verdict=verified['verdict'], result_sha256=verified['source_report_sha256'],
                        artifact_sha256=verified['candidate_tree_sha256'],
                        failure_class='BUSINESS' if verified['verdict'] == 'FAIL' else None,
                        independent_run_id=verified['run_id'], source_manifest_sha256=verified['source_manifest_sha256'])
            nodes[authority['id']] = authority
            ev = n('Evidence', 'evidence', revision_id=rev['id'], outcome_id=outcome['id'],
                   artifact_sha256=outcome['artifact_sha256'], strategy_sha256=rule['strategy_sha256'])
            for rel, a, b in [('SUPPORTED_BY' if verified['verdict'] == 'PASS' else 'COUNTEREXAMPLE', rev, ev),
                              ('VERIFIES', ev, outcome), ('IN_CONTEXT', outcome, ctx),
                              ('FOR_TASK', ctx, task), ('ATTESTED_BY', outcome, authority)]: link(rel, a, b)
            self.pins.put('outcomes', outcome['id'], digest(outcome))
            for f in review['facts'].values():
                if f['availability']=='KNOWN':self.pins.put('fact_sources', digest(f), f['authority_ref'])
        require(len(nodes) <= 8192 and len(edges) <= 8192, 'CAPACITY_EXCEEDED')
        for v in nodes.values(): self.repo.put_node(v)
        # NO semantic links are staged against active versions: old readers
        # remain valid while a complete immutable preparation is assembled.
        next_epoch = state['epoch'] + 1
        manifest = self.repo.put_document('PublicationManifest', ['manifest', publication_key],
                     dict(nodes={i:digest(n) for i,n in nodes.items()}, edges={i:digest(e) for i,e in edges.items()}),
                     experience_id=exp['id'], epoch=next_epoch, source_namespace='VERIFIED_HOST_PUBLICATION')
        self.pins.put('publications', manifest['id'], digest(manifest))
        heads = copy.deepcopy(state['discovery_heads']); listing = {}
        if token in heads:
            root = self.repo.node(heads[token]['id']); require(digest(root) == heads[token]['sha256'])
            listing = self.repo.load_document(root)
        listing[exp['id']] = dict(manifest_id=manifest['id'], manifest_sha256=digest(manifest))
        require(len(listing) <= 256, 'CAPACITY_EXCEEDED')
        cat = self.repo.put_document('QuerySnapshot', ['catalogue', publication_key, token], listing,
                                     document_kind='DISCOVERY_CATALOGUE', scope_token=token, epoch=next_epoch)
        heads[token] = dict(id=cat['id'], sha256=digest(cat))
        require(len(heads) <= 1024, 'CAPACITY_EXCEEDED')
        new_state = {**state, 'epoch':next_epoch, 'discovery_heads':heads}
        target = 'WITHDRAWN' if governance and governance['event_type'] == 'withdraw' and nodes[governance['target_id']]['kind']=='ExperienceRevision' else 'PUBLISHED'
        # Governance of an Evidence keeps the candidate published; revision
        # withdrawal is terminal, requiring a new Candidate for a new revision.
        previous = self.repo.node(h['event_id'])
        event = record(self.repo.tenant, 'CandidateEvent', ['commit', publication_key], candidate_id=candidate,
                       sequence=h['sequence']+1, state=target, previous_event=previous['id'],
                       request_body_sha256=request_sha, principal=self.grant.principal,
                       reason=governance['reason'] if governance else review['reason'], visibility='HOST_ONLY')
        new_head = {**h, 'state':target, 'sequence':event['sequence'], 'event_id':event['id']}
        activation = [edge(self.repo.tenant,'PUBLISHED_BY',v,manifest) for v in nodes.values()
                      if v['kind'] in {'ExperienceRevision','GovernanceEvent'}]
        activation += [edge(self.repo.tenant,'COMMITS',state,manifest,manifest_sha256=digest(manifest)),
                       edge(self.repo.tenant,'HAS_CANDIDATE_EVENT',c,event),
                       edge(self.repo.tenant,'PREVIOUS_EVENT',event,previous)]
        # Validate every typed path on the virtual complete graph BEFORE fence.
        paths=[]
        for e in edges.values():
            if e['kind'] not in {'SUPPORTED_BY','COUNTEREXAMPLE','OBSERVED_OUTCOME'}: continue
            def one(x, rel):
                ee=[a for a in edges.values() if a['kind']==rel and a['source_id']==x['id']]
                require(len(ee)==1); return ee[0],nodes[ee[0]['target_id']]
            rr=nodes[e['source_id']];ev=nodes[e['target_id']]
            ve,o=one(ev,'VERIFIES');ice,ct=one(o,'IN_CONTEXT');ft,task=one(ct,'FOR_TASK');at,au=one(o,'ATTESTED_BY')
            paths.append([native(x) for x in [rr,e,ev,ve,o,ice,ct,ft,task,at,au]])
        validate_witness(dict(nodes=nodes,edges=edges,experience_id=exp['id'],paths=paths),self.repo.registry,self.repo.tenant)
        superseded_heads=[]
        for rid in supersedes:
            old_candidate=nodes[rid].get('candidate_id')
            if not old_candidate:
                continue  # Historical read-only fixtures have no native Candidate lifecycle.
            require(old_candidate != candidate, 'INVALID_TRANSITION')
            old_head=self.head(old_candidate)
            if old_head['state']!='PUBLISHED':
                require(old_head['state'] in {'WITHDRAWN','SUPERSEDED'}, 'INVALID_TRANSITION')
                continue
            old_c=self.repo.node(old_candidate);old_prev=self.repo.node(old_head['event_id'])
            old_ev=record(self.repo.tenant,'CandidateEvent',['superseded',publication_key,old_candidate],
                          candidate_id=old_candidate,state='SUPERSEDED',sequence=old_head['sequence']+1,
                          previous_event=old_prev['id'],reason='Explicit trusted revision supersession',
                          request_body_sha256=request_sha,visibility='HOST_ONLY')
            updated={**old_head,'state':'SUPERSEDED','event_id':old_ev['id'],'sequence':old_ev['sequence']}
            superseded_heads.append(dict(candidate=old_c,previous=old_prev,old=old_head,new=updated,event=old_ev))
            activation += [edge(self.repo.tenant,'HAS_CANDIDATE_EVENT',old_c,old_ev),
                           edge(self.repo.tenant,'PREVIOUS_EVENT',old_ev,old_prev)]
        document = dict(semantic=semantic,request_key=request_key,request_body_sha256=request_sha,
                        candidate=c,head=h,previous=previous,source=source,outcome=op,review=review,
                        authority=authority,capability=cap,state=state,new_state=new_state,
                        new_head=new_head,event=event,manifest=manifest,catalogue=cat,
                        nodes=nodes,prior_edges=prior_edges,superseded_heads=superseded_heads,
                        validation_nodes=validation_nodes,validation_edges=validation_edges,validation_documents=list(validation_documents.values()),
                        new_edges=[e for i,e in edges.items() if i not in prior_edges]+activation,
                        receipt_id=receipt_id)
        root = self.repo.put_document('QuerySnapshot',
                                      ['prepared',publication_key],document,document_kind='HOST_PREPARED',
                                      visibility='HOST_ONLY')
        # Review, source, Outcome and all prepared chunks are pinned by final
        # query; private root digest is not an Agent-provided authority.
        self.pins.put('preparations',root['id'],digest(root))
        return Prepared(root['id'], digest(root))

    def publish(self, prepared):
        state, cap = self._check()
        require(type(prepared) is Prepared, 'UNAUTHORIZED')
        root = self.repo.node(prepared.identifier); require(digest(root)==prepared.sha256)
        require(PinMap(self.pins.root,'preparations').get(root['id'])==digest(root),'UNAUTHORIZED')
        require(root['document_kind']=='HOST_PREPARED' and root['visibility']=='HOST_ONLY', 'UNAUTHORIZED')
        doc = self.repo.load_document(root)
        receipt_id=doc['receipt_id']
        rows=self.repo.execute('Q13',id=receipt_id)
        if rows:
            receipt=self.repo.node(receipt_id)
            require(receipt['request_body_sha256']==doc['request_body_sha256'],'IMMUTABLE_CONFLICT')
            return receipt
        self._check(doc['review']['approved_scope'])
        require(doc['capability']==cap and doc['semantic']['principal']==self.grant.principal,'UNAUTHORIZED')
        _,au,out=self._verified(doc['candidate']['id'],doc['authority']['id'],doc['source']['report_reference'])
        require(digest(out)==doc['source']['outcome_pin'] and au==doc['authority'])
        require(state==doc['state'],'CONFLICT')
        require(self.head(doc['candidate']['id'])==doc['head'],'CONFLICT')
        # Re-read every manifest/chunk/catalogue and cross-check prepared pins.
        listing=self.repo.load_document(doc['manifest']); catalogue=self.repo.load_document(doc['catalogue'])
        require(listing['nodes']=={i:digest(v) for i,v in doc['nodes'].items()})
        require(catalogue[doc['manifest']['experience_id']]==dict(manifest_id=doc['manifest']['id'],manifest_sha256=digest(doc['manifest'])))
        receipt=record(self.repo.tenant,'SourceVerification',['publication-request',self.grant.principal,doc['request_key']],
                       verification='PUBLICATION_COMMITTED',request_body_sha256=doc['request_body_sha256'],
                       prepared_id=root['id'],prepared_sha256=digest(root),candidate_id=doc['candidate']['id'],
                       event_id=doc['event']['id'],epoch=doc['new_state']['epoch'],
                       manifest_id=doc['manifest']['id'],experience_id=doc['manifest']['experience_id'],
                       new_head_sha256=digest(doc['new_head']),visibility='HOST_ONLY')
        pinned=[root,doc['candidate'],doc['head'],doc['previous'],doc['source'],doc['outcome'],doc['review'],doc['authority'],cap,doc['manifest'],doc['catalogue'],*doc['nodes'].values()]
        pinned += list(doc['validation_nodes'].values())
        heads=[(doc['head'],doc['new_head'])]
        events=[doc['event'],receipt]
        for item in doc['superseded_heads']:
            pinned += [item[k] for k in ['candidate','previous','old']]
            heads.append((item['old'],item['new']));events.append(item['event'])
        from .publication_fence import activate
        rows=activate(self.repo,old_state=doc['state'],new_state=doc['new_state'],capability=cap,
                      pinned=pinned,documents=[root,doc['manifest'],doc['catalogue'],*doc['validation_documents']],
                      current_ids=set(doc['nodes'])|set(doc['validation_nodes']),prior_edges={**doc['validation_edges'],**doc['prior_edges']},
                      create_nodes=events,create_edges=doc['new_edges'],heads=heads,current_verifier_ids=[doc['authority']['id']])
        if not rows:
            old=self.repo.execute('Q13',id=receipt_id)
            if old:
                rec=self.repo.node(receipt_id);require(rec['request_body_sha256']==doc['request_body_sha256'],'IMMUTABLE_CONFLICT');return rec
            raise V2Error('CONFLICT')
        require(rows==[[digest(doc['new_state'])]])
        actual=self.repo.node(receipt_id);require(actual==receipt)
        return actual


    def govern(self, candidate, review_id, *, experience_id, target_id, event_type,
               bounded_scope, reason, request_key):
        head = self.head(candidate)
        return self.prepare(candidate, review_id, request_key=request_key,
                            expected_head=digest(head), expected_epoch=self.repo.state()['epoch'],
                            experience_id=experience_id,
                            governance=dict(event_type=event_type,target_id=target_id,
                                            scope=bounded_scope,reason=reason))

    def revoke_capability(self, *, reason):
        state, cap = self._check()
        new_state = {**state, 'authz_epoch':state['authz_epoch']+1}
        new_cap = {**cap, 'state':'REVOKED'}
        ev=record(self.repo.tenant,'SourceVerification',['revocation',cap['id'],digest(state)],
                  verification='HOST_CAPABILITY_REVOKED',capability_id=cap['id'],reason=reason,
                  principal=self.grant.principal,authz_epoch=new_state['authz_epoch'],visibility='HOST_ONLY')
        self.repo.put_node(ev)
        rows=self.repo.transport.query('MATCH(s:TenantState {id:$s}),(a:Authority {id:$a}) '
            'WHERE properties(s)=$old AND properties(a)=$oldcap SET s=$new,a=$newcap RETURN s.authz_epoch',
            dict(s=state['id'],a=cap['id'],old=native(state),oldcap=native(cap),new=native(new_state),newcap=native(new_cap)),read_only=False)
        require(rows==[[new_state['authz_epoch']]],'CONFLICT')
        return ev

    def prepare_authority_withdrawal(self, authority_id, *, reason, request_key, expected_epoch):
        """Bounded tenant-wide negative governance; never rewrites an Outcome.

        Every affected Evidence gets an immutable scoped withdrawal and fresh
        complete manifest. All catalogues, heads and authz/semantic epochs are
        activated in the same query. An oversized preparation fails closed.
        """
        state,cap=self._check();authority=self.repo.node(authority_id)
        require(authority['kind']=='Authority' and self.repo.registry.authorities.get(authority_id)==digest(authority),'UNAUTHORIZED')
        semantic=dict(tenant=self.repo.tenant,principal=self.grant.principal,authority_id=authority_id,
                      reason=reason,request_key=request_key,expected_epoch=expected_epoch)
        key=['authority-withdrawal',self.grant.principal,request_key]
        root_id=identity(self.repo.tenant,'QuerySnapshot',key)
        if self.repo.execute('Q13',id=root_id):
            old=self.repo.node(root_id);doc=self.repo.load_document(old)
            require(doc['semantic']==semantic,'IMMUTABLE_CONFLICT');return Prepared(root_id,digest(old))
        require(state['epoch']==expected_epoch,'CONFLICT')
        require(authority_id not in state.get('revoked_authorities',[]),'INVALID_TRANSITION')
        issuer_scope=authority.get('scope')
        require(isinstance(issuer_scope,dict),'REREGISTRATION_REQUIRED')
        values=issuer_scope.get('task.shared_state_kind')
        tokens=sorted(set(['*',*[digest(['task.shared_state_kind',v]) for v in values]])) if values else sorted(state['discovery_heads'])
        witnesses=[];validation_nodes={};validation_edges={};validation_documents={}
        for token in tokens:
            for eid in self.repo.discover_partitions([token],state):
                witness=self.repo.read_witness(eid,state)
                validation_nodes.update(witness['nodes']);validation_edges.update(witness['edges'])
                validation_documents[witness['manifest']['id']]=witness['manifest']
                catalogue=self.repo.node(witness['discovery_ref']['catalogue_id']);validation_documents[catalogue['id']]=catalogue
                if any(n['kind']=='VerifiedOutcome' and n['authority_ref']==authority_id for n in witness['nodes'].values()):witnesses.append(witness)
                require(len(witnesses)<=256,'CAPACITY_EXCEEDED')
        require(self.repo.state()==state,'CONFLICT')
        all_nodes={};all_edges={};new_edges=[];documents=[];heads=[];events=[];manifests=[];head_candidates=set()
        updates={};affected=[]
        for w in witnesses:
            targets=[]
            for e in w['edges'].values():
                if e['kind']!='VERIFIES':continue
                outcome=w['nodes'][e['target_id']]
                if outcome['authority_ref']==authority_id:targets.append(w['nodes'][e['source_id']])
            if not targets:continue
            ns=dict(w['nodes']);es=dict(w['edges']);all_nodes.update(ns);all_edges.update(es)
            affected.append(w['experience_id'])
            for ev in targets:
                revision=ns[ev['revision_id']];self._check(revision['scope'])
                g=record(self.repo.tenant,'GovernanceEvent',[key,ev['id']],event_type='withdraw',
                         target_id=ev['id'],target_label='Evidence',scope=revision['scope'],
                         reason=reason,effective_at=utc_now(),withdrawn_authority_id=authority_id)
                self.repo.put_node(g);ns[g['id']]=g;all_nodes[g['id']]=g
                link=edge(self.repo.tenant,'GOVERNS',g,ev);es[link['id']]=link;new_edges.append(link)
                cid=revision.get('candidate_id')
                if cid and cid not in head_candidates:
                    old=self.head(cid);prev=self.repo.node(old['event_id']);candidate=self.repo.node(cid)
                    event=record(self.repo.tenant,'CandidateEvent',[key,cid],candidate_id=cid,
                                 state=old['state'],sequence=old['sequence']+1,previous_event=prev['id'],
                                 event_type='AUTHORITY_EVIDENCE_WITHDRAWAL',state_change=False,
                                 reason=reason,visibility='HOST_ONLY')
                    new={**old,'event_id':event['id'],'sequence':event['sequence']}
                    heads.append(dict(old=old,new=new,candidate=candidate,previous=prev))
                    events.append(event);head_candidates.add(cid)
                    new_edges += [edge(self.repo.tenant,'HAS_CANDIDATE_EVENT',candidate,event),
                                  edge(self.repo.tenant,'PREVIOUS_EVENT',event,prev)]
            manifest=self.repo.put_document('PublicationManifest',[key,w['experience_id']],
                dict(nodes={i:digest(n) for i,n in ns.items()},edges={i:digest(e) for i,e in es.items()}),
                experience_id=w['experience_id'],epoch=state['epoch']+1,source_namespace='TRUSTED_AUTHORITY_WITHDRAWAL')
            self.pins.put('publications',manifest['id'],digest(manifest));manifests.append(manifest)
            documents.append(w['manifest']);all_nodes[w['manifest']['id']]=w['manifest']
            for n in ns.values():
                if n['kind'] in {'ExperienceRevision','GovernanceEvent'}:new_edges.append(edge(self.repo.tenant,'PUBLISHED_BY',n,manifest))
            new_edges.append(edge(self.repo.tenant,'COMMITS',state,manifest,manifest_sha256=digest(manifest)))
            token=ns[w['experience_id']]['scope_token']
            if token not in updates:
                oldroot=self.repo.node(state['discovery_heads'][token]['id'])
                require(digest(oldroot)==state['discovery_heads'][token]['sha256'])
                documents.append(oldroot);updates[token]=self.repo.load_document(oldroot)
            updates[token][w['experience_id']]=dict(manifest_id=manifest['id'],manifest_sha256=digest(manifest))
        newheads=copy.deepcopy(state['discovery_heads']);catalogues=[]
        for token,listing in updates.items():
            cat=self.repo.put_document('QuerySnapshot',[key,token],listing,
                document_kind='DISCOVERY_CATALOGUE',scope_token=token,epoch=state['epoch']+1)
            catalogues.append(cat);newheads[token]=dict(id=cat['id'],sha256=digest(cat))
        new_state={**state,'epoch':state['epoch']+1,'authz_epoch':state['authz_epoch']+1,
                   'discovery_heads':newheads,'revoked_authorities':sorted(set(state.get('revoked_authorities',[]))|{authority_id})}
        doc=dict(semantic=semantic,state=state,new_state=new_state,capability=cap,authority=authority,
                 nodes=all_nodes,prior_edges=all_edges,new_edges=new_edges,documents=documents+manifests+catalogues,
                 events=events,heads=heads,affected=affected,receipt_key=key,validation_nodes=validation_nodes,validation_edges=validation_edges,validation_documents=list(validation_documents.values()))
        root=self.repo.put_document('QuerySnapshot',key,doc,document_kind='HOST_AUTHORITY_WITHDRAWAL',visibility='HOST_ONLY')
        self.pins.put('preparations',root['id'],digest(root))
        return Prepared(root['id'],digest(root))

    def commit_authority_withdrawal(self, prepared):
        state,cap=self._check();require(type(prepared) is Prepared,'UNAUTHORIZED')
        root=self.repo.node(prepared.identifier);require(digest(root)==prepared.sha256 and root['document_kind']=='HOST_AUTHORITY_WITHDRAWAL')
        require(PinMap(self.pins.root,'preparations').get(root['id'])==digest(root),'UNAUTHORIZED')
        doc=self.repo.load_document(root)
        receipt_id=identity(self.repo.tenant,'SourceVerification',doc['receipt_key'])
        if self.repo.execute('Q13',id=receipt_id):
            receipt=self.repo.node(receipt_id);require(receipt['request_body_sha256']==digest(doc['semantic']),'IMMUTABLE_CONFLICT')
            return receipt
        require(state==doc['state'] and cap==doc['capability'],'CONFLICT')
        require(doc['semantic']['principal']==self.grant.principal,'UNAUTHORIZED')
        receipt=record(self.repo.tenant,'SourceVerification',doc['receipt_key'],
                       verification='AUTHORITY_WITHDRAWAL_COMMITTED',request_body_sha256=digest(doc['semantic']),
                       affected_experience_ids=doc['affected'],authority_id=doc['authority']['id'],
                       epoch=doc['new_state']['epoch'],authz_epoch=doc['new_state']['authz_epoch'],
                       prepared_id=root['id'],prepared_sha256=digest(root),visibility='HOST_ONLY')
        pins=[root,doc['authority'],*doc['nodes'].values(),*doc['validation_nodes'].values()]
        for item in doc['heads']:
            pins += [item[k] for k in ['old','candidate','previous']]
        from .publication_fence import activate
        rows=activate(self.repo,old_state=state,new_state=doc['new_state'],capability=cap,
                      pinned=pins,documents=[root,*doc['documents'],*doc['validation_documents']],current_ids=set(doc['nodes'])|set(doc['validation_nodes']),
                      prior_edges={**doc['validation_edges'],**doc['prior_edges']},create_nodes=[receipt,*doc['events']],
                      create_edges=doc['new_edges'],heads=[(h['old'],h['new']) for h in doc['heads']])
        if not rows:
            if self.repo.execute('Q13',id=receipt_id):return self.repo.node(receipt_id)
            raise V2Error('CONFLICT')
        require(rows==[[digest(doc['new_state'])]])
        return self.repo.node(receipt_id)
