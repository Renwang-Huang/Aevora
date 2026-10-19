from dataclasses import replace
import copy
import pytest
from aevora.contracts import *
from aevora.orderflow_outcome_bridge import OutcomeVerificationError
from aevora_maintainer.host_v2 import TrustedHost, Prepared
from tools.validation.g22_fixture import proposal,admitted,ready

@pytest.mark.parametrize('field,value', [('run_id','forged-run'),('tree_sha','0'*64),('patch_sha','f'*64)])
def test_real_oracle_source_mismatch_never_mints_outcome(host,field,value):
    args=dict(run_id=host.case['run_id'],tree_sha=host.case['tree_sha']);args[field]=value
    c=host.propose(proposal(),**args)
    with pytest.raises(V2Error):host.verify_source(c['id'],host.verifier.authority_id,'evaluation_report.json')
    assert host.repo.transport.query('MATCH(o:VerifiedOutcome) RETURN count(o)')==[[0]]


def test_unregistered_verifier_cannot_self_certify(host):
    c=host.propose(proposal(),run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    with pytest.raises(V2Error,match='UNAUTHORIZED'):host.verify_source(c['id'],'fake-verifier','evaluation_report.json')


def test_agent_origin_requires_native_evidence_not_self_report(host):
    c=host.propose(proposal(),run_id=host.case['run_id'],tree_sha=host.case['tree_sha'],origin='AGENT_PROPOSED',native_candidate_id='fake-agent-claim')
    with pytest.raises((V2Error,OutcomeVerificationError)):host.verify_source(c['id'],host.verifier.authority_id,'evaluation_report.json')
    assert host.repo.transport.query('MATCH(o:VerifiedOutcome) RETURN count(o)')==[[0]]


def test_candidate_immutable_key_replay_and_body_conflict(host):
    p=proposal();c=host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    assert host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])==c
    p['strategy']='different meaning'
    with pytest.raises(V2Error,match='IMMUTABLE_CONFLICT'):host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])


def test_review_scope_widening_rejected(host):
    p=proposal();p['scope']['task.concurrency_scope']=['single_process_multi_thread']
    c=host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    s=host.verify_source(c['id'],host.verifier.authority_id,'evaluation_report.json');o=host.verify_outcome(c['id'],s['id'])
    with pytest.raises(V2Error,match='SCOPE_WIDENING'):
        host.review(c['id'],s['id'],o['id'],approved_scope={'task.shared_state_kind':['sqlite_file']},reason='widening')


def test_unknown_necessary_premise_stays_pending(host):
    p=proposal();p['necessary_conditions']['task.clock_domain']=['monotonic']
    c,s,o,r=admitted(host,p=p)
    assert r['status']=='PENDING' and host.head(c['id'])['state']=='EVIDENCE_PENDING'

@pytest.mark.parametrize('field,value',[('tenant','other-tenant'),('profile','aevora.mcp/FAKE'),('generation','wrong'),('authz_epoch',99),('valid_until','2020-01-01T00:00:00Z')])
def test_host_capability_binding_rejected(host,field,value):
    with pytest.raises(V2Error,match='UNAUTHORIZED'):
        TrustedHost(host.repo,host.pins.root,replace(host.grant,**{field:value}),host.verifiers.values())


def test_public_dict_is_not_prepared_authority(host):
    with pytest.raises(V2Error,match='UNAUTHORIZED'):host.publish({'identifier':'fake','sha256':'0'*64})


def test_terminal_candidate_cannot_resurrect(host):
    c=host.propose(proposal(),run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    h=host.head(c['id']);h=host.transition(c['id'],'REJECTED',expected_head=digest(h),reason='No admissible evidence')
    with pytest.raises(V2Error,match='INVALID_TRANSITION'):
        host.transition(c['id'],'EVIDENCE_PENDING',expected_head=digest(h),reason='resurrection')


def test_candidate_body_replacement_fails_host_immutable_pin(host):
    c=host.propose(proposal(),run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    changed=copy.deepcopy(c);changed['body']['strategy']='Unverified replacement strategy'
    changed['body_sha256']=digest(changed['body'])
    host.repo.transport.query('MATCH(n:Candidate {id:$id}) SET n=$row',dict(id=c['id'],row=native(changed)),read_only=False)
    with pytest.raises(V2Error,match='SOURCE_MISMATCH'):host.verify_source(c['id'],host.verifier.authority_id,'evaluation_report.json')
    assert host.repo.transport.query('MATCH(o:VerifiedOutcome) RETURN count(o)')==[[0]]


def test_review_approval_replacement_rejected_by_external_host_pin(host):
    c,s,o,r=admitted(host)
    altered={**r,'reason':'Altered review after trusted approval'}
    host.repo.transport.query('MATCH(n:SourceVerification {id:$id}) SET n=$row',dict(id=r['id'],row=native(altered)),read_only=False)
    h=host.transition(c['id'],'PUBLISHING',expected_head=digest(host.head(c['id'])),reason='Attempt modified review')
    with pytest.raises(V2Error,match='UNAUTHORIZED'):
        host.prepare(c['id'],r['id'],request_key='modified-review',expected_head=digest(h),expected_epoch=0)
    assert host.repo.state()['epoch']==0


def test_scope_limited_capability_cannot_publish_wider_partition(host):
    p=proposal();p['scope']={'task.shared_state_kind':['redis']}
    with pytest.raises(V2Error,match='UNAUTHORIZED'):
        host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])


def test_new_host_generation_rotates_registered_verifier_without_rewriting_old(host,tmp_path):
    old=host.repo.node(host.verifier.authority_id)
    grant=TrustedHost.bootstrap(host.repo,host.pins.root,principal=host.grant.principal,
                               allowed_scope={'task.shared_state_kind':['sqlite_file']},generation='two')
    renewed=TrustedHost(host.repo,host.pins.root,grant)
    fresh=renewed.register_orderflow(host.anchor,host.case['evaluator_sha'],host.case['suite_sha'])
    assert fresh.authority_id!=host.verifier.authority_id
    assert host.repo.node(host.verifier.authority_id)==old


def test_historical_issuer_window_is_verified_at_certificate_issuance(v2):
    # Explicit synthetic calendar contract, not a new engineering Outcome.
    a=record(v2.tenant,'Authority','calendar-issuer',created='2020-01-01T00:00:00Z',
             source='HOST_CONTROLLED_SYNTHETIC_FIXTURE',authority_class='ENGINEERING_VERIFIER',
             independence='INDEPENDENT',state='ACTIVE',verifier_version='synthetic',source_sha256='a'*64,
             valid_from='2020-01-01T00:00:00Z',valid_until='2020-02-01T00:00:00Z')
    o=record(v2.tenant,'VerifiedOutcome','calendar-certificate',authority=a['id'],created='2020-01-02T00:00:00Z',
             source='HOST_CONTROLLED_SYNTHETIC_FIXTURE',task_id='task:synthetic',verdict='PASS',
             result_sha256='b'*64,artifact_sha256='c'*64,failure_class=None)
    v2.registry.authorities[a['id']]=digest(a);v2.registry.outcomes[o['id']]=digest(o)
    v2.registry.verify_outcome(o,a)
    bad={**o,'created_at':'2020-02-02T00:00:00Z'};v2.registry.outcomes[bad['id']]=digest(bad)
    with pytest.raises(V2Error):v2.registry.verify_outcome(bad,a)


def test_registered_wrong_suite_pin_cannot_admit_real_outcome(host):
    wrong=host.register_orderflow(host.anchor,host.case['evaluator_sha'],'f'*64)
    c=host.propose(proposal(),run_id=host.case['run_id'],tree_sha=host.case['tree_sha'])
    with pytest.raises(V2Error,match='SOURCE_MISMATCH'):host.verify_source(c['id'],wrong.authority_id,'evaluation_report.json')
    assert host.repo.transport.query('MATCH(o:VerifiedOutcome) RETURN count(o)')==[[0]]


def test_ordinary_self_test_report_cannot_become_verified_outcome(host,tmp_path):
    import json,hashlib
    from aevora.orderflow_outcome_bridge import TrustAnchor
    root=tmp_path/'ordinary-self-test';root.mkdir()
    report=root/'evaluation_report.json';report.write_text(json.dumps(dict(run_id=root.name,episode_id='ORDINARY_PROJECT',evaluation_status='PASS',public_self_tests_passed=7)))
    manifest=root/'MANIFEST.json';manifest.write_text(json.dumps(dict(files={'evaluation_report.json':hashlib.sha256(report.read_bytes()).hexdigest()})))
    fake=TrustAnchor(root,hashlib.sha256(manifest.read_bytes()).hexdigest(),{'evaluation_report.json':root.name},profile='current_live',manifest_relative_path='MANIFEST.json')
    verifier=host.register_orderflow(fake,host.case['evaluator_sha'],host.case['suite_sha'])
    c=host.propose(proposal(),run_id=root.name,tree_sha='a'*64)
    with pytest.raises(OutcomeVerificationError):host.verify_source(c['id'],verifier.authority_id,'evaluation_report.json')
    assert host.repo.transport.query('MATCH(o:VerifiedOutcome) RETURN count(o)')==[[0]]
