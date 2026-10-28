"""Host-authorized independent project evidence; no candidate execution or MCP API.

The receipt pin must arrive from a trusted verifier channel. Hashing an Agent's
self-report does not establish that channel. Policy is protected Host configuration.
"""
from pathlib import Path
import os
import stat

from .candidate import CandidateLifecycle
from .models import (InvalidRecord, PUBLIC_CONTEXT_FACTS, canonical_json, digest,
                     normalize_context, parse_timestamp, validate_id, validate_record)
from .source_evidence import EvidenceFiles, _digest, _json, _require, read_junit

POLICY_VERSION = 'aevora.project-source-policy/1'
RECEIPT_VERSION = 'aevora.project-source-receipt/1'
VERIFIER_VERSION = 'AevoraProjectSource/1'
ARTIFACT_LIMITS = {'submission': 32*1024**2, 'suite': 8*1024**2,
                   'evaluator': 1024**2, 'junit': 8*1024**2}


def validate_policy(policy):
    _require(isinstance(policy, dict) and set(policy) == {
        'schema_version', 'verifier_id', 'origin', 'suite_sha256',
        'evaluator_sha256', 'required_tests', 'facts'}, 'Invalid project source policy fields')
    _require(policy['schema_version'] == POLICY_VERSION, 'Unsupported project source policy')
    validate_id(policy['verifier_id'])
    _require(policy['origin'] in {'independent_project', 'synthetic_or_test_fixture'},
             'Project source cannot claim a natural native Agent run')
    _digest(policy['suite_sha256']); _digest(policy['evaluator_sha256'])
    tests = policy['required_tests']
    _require(isinstance(tests, list) and 0 < len(tests) <= 1000 and
             all(isinstance(t, str) and 0 < len(t) <= 512 and '::' in t for t in tests) and
             len(set(tests)) == len(tests), 'Complete unique JUnit classname::name identities required')
    facts = normalize_context(policy['facts'])
    _require(bool(facts) and not set(facts)-PUBLIC_CONTEXT_FACTS, 'Public independently verified facts required')
    return policy


def load_policy(path):
    """A policy is Host configuration, separate from candidate/CI artifact input."""
    path = Path(path).absolute()
    with_files = EvidenceFiles(path.parent)
    try:
        info = os.fstat(with_files.fd)
        _require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                 'Policy directory must be owned by Host and mode 0700')
        info = os.stat(path.name, dir_fd=with_files.fd, follow_symlinks=False)
        _require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                 'Policy file must be owned by Host and mode 0600')
        return validate_policy(_json(with_files.read(path.name, 256*1024)))
    finally:
        with_files.close()


def verify_project_candidate(repo, candidate_id, *, policy, evidence_root, receipt_sha256):
    """Check every input before writing; retry the same immutable plan after interruption."""
    policy = validate_policy(policy)
    _digest(receipt_sha256)
    view = CandidateLifecycle(repo).inspect(candidate_id)
    candidate = view['candidate']
    archive = EvidenceFiles(Path(evidence_root))
    try:
        receipt = _json(archive.read('receipt.json', 256*1024, receipt_sha256))
        _require(isinstance(receipt, dict) and set(receipt) == {
            'schema_version', 'candidate_id', 'candidate_body_sha256', 'run_id',
            'verifier_id', 'origin', 'facts', 'started_at', 'ended_at', 'exit_code', 'artifacts'},
            'Invalid project receipt fields; verdict/verified claims are not accepted')
        _require(receipt['schema_version'] == RECEIPT_VERSION, 'Unsupported project receipt')
        _require(receipt['candidate_id'] == candidate_id and
                 receipt['candidate_body_sha256'] == candidate['body_sha256'] and
                 receipt['run_id'] == candidate['run_id'], 'Receipt belongs to another candidate or Run')
        _require(receipt['verifier_id'] == policy['verifier_id'] and receipt['origin'] == policy['origin'],
                 'Verifier identity or origin differs from Host policy')
        _require(canonical_json(receipt['facts']) == canonical_json(policy['facts']),
                 'Receipt facts differ from independently established Host facts')
        start = parse_timestamp(receipt['started_at']); end = parse_timestamp(receipt['ended_at'])
        _require(end >= start, 'Invalid verifier execution interval')
        code = receipt['exit_code']
        _require(type(code) is int and 0 <= code <= 255, 'Actual bounded process exit code required')
        artifacts = receipt['artifacts']
        _require(isinstance(artifacts, dict) and set(artifacts) == set(ARTIFACT_LIMITS),
                 'Submission, trusted suite, evaluator and JUnit artifacts required')
        junit = None
        for name, limit in ARTIFACT_LIMITS.items():
            ref = artifacts[name]
            _require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'Invalid artifact reference')
            _digest(ref['sha256'])
            if name in {'suite', 'evaluator'}:
                _require(ref['sha256'] == policy[name+'_sha256'], 'Suite or evaluator differs from Host policy')
            data = archive.read(ref['path'], limit, ref['sha256'])
            _require(bool(data), 'Empty verifier artifact refused')
            if name == 'junit': junit = data
        _require(len({r['path'] for r in artifacts.values()}) == len(artifacts),
                 'Verifier artifact identities must be distinct')
        tests = read_junit(junit, policy['required_tests'], identity='nodeid')
        if code == 0:
            _require(tests['passed'] == tests['collected'], 'Zero exit with non-PASS tests is inconsistent')
            verdict = 'PASS'
        elif code == 1 and tests['failed'] and not tests['errors'] and not tests['skipped']:
            verdict = 'FAIL'
        else:
            verdict = 'ERROR'
    finally:
        archive.close()

    suffix = digest([VERIFIER_VERSION, candidate_id, receipt_sha256, policy])
    origin = policy['origin']
    outcome = {
        'id': 'project-outcome:'+suffix, 'run_id': candidate['run_id'], 'verdict': verdict,
        'submission_digest': artifacts['submission']['sha256'],
        'evaluator_fingerprint': policy['evaluator_sha256'], 'test_suite_fingerprint': policy['suite_sha256'],
        'verifier_identity': VERIFIER_VERSION, 'source_type': origin, 'attribution': 'UNKNOWN',
        'test_count': tests['collected'], 'test_counts': {k:tests[k] for k in ('passed','failed','errors','skipped')},
        'source_receipt_sha256': receipt_sha256, 'source_policy_sha256': digest(policy),
        'junit_sha256': artifacts['junit']['sha256'], 'evaluated_at': receipt['ended_at'],
        'assurance': 'Host-authorized independent verifier receipt and pinned artifacts; not runtime attestation',
    }
    context = {'id':'context:project-source:'+suffix, 'facts':policy['facts'], 'source_type':origin}
    task = {'id':'task:project-source:'+suffix, 'public_title':'Independent project verification in a bounded factual scope'}
    source = {
        'id':'source-verification:project:'+suffix, 'candidate_id':candidate_id, 'run_id':candidate['run_id'],
        'authority':'TRUSTED_HOST_SOURCE_VERIFIER', 'origin':origin, 'facts':policy['facts'],
        'source_sha256':receipt_sha256, 'submission_sha256':outcome['submission_digest'], 'outcome_id':outcome['id'],
        'verifier_id':policy['verifier_id'], 'verifier_version':VERIFIER_VERSION,
        'source_epoch':'project-receipt:sha256:'+receipt_sha256,
        'native_thread_id':'UNAVAILABLE', 'causal_benefit':'UNKNOWN',
    }
    records = [('VerifiedOutcome',outcome), ('Context',context), ('Task',task), ('SourceVerification',source)]
    for label, record in records: validate_record(label, record)
    for label, record in records: repo.put_node(label, record)
    repo.put_edge('IN_CONTEXT','VerifiedOutcome',outcome['id'],'Context',context['id'])
    repo.put_edge('FOR_TASK','Context',context['id'],'Task',task['id'])
    # Last link makes the fully materialized source available to admission.
    repo.put_edge('HAS_SOURCE_VERIFICATION','Candidate',candidate_id,'SourceVerification',source['id'])
    return {'status':'SOURCE_VERIFIED', 'source':source, 'outcome_verdict':verdict,
            'admission':'ELIGIBLE_FOR_BOUNDED_REVIEW' if verdict=='PASS' else 'BLOCKED_NON_PASS',
            'lifecycle_state':view['head']['state'], 'agent_adoption':'UNKNOWN', 'causal_benefit':'UNKNOWN'}
