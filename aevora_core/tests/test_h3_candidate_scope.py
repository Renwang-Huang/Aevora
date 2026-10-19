"""Real-graph negative-condition controls; explicitly synthetic source fixtures."""
import pytest
from test_h3_lifecycle import life,proposal,move,grant,FACTS
from aevora.experience_resolver import ExperienceResolver


def publish_scoped(life,body,facts):
    cid=life.propose('scope-fixture-run',body)['candidate_id'];move(life,cid,'EVIDENCE_PENDING','pending')
    s={'id':'source:scope-fixture','run_id':'scope-fixture-run','authority':'TRUSTED_HOST_SOURCE_VERIFIER',
        'origin':'synthetic_or_test_fixture','source_sha256':'a'*64,'submission_sha256':'b'*64,
        'outcome_id':'outcome:scope-fixture','facts':facts}
    life.repo.put_node('SourceVerification',s)
    life.repo.put_node('VerifiedOutcome',{'id':s['outcome_id'],'run_id':s['run_id'],'verdict':'PASS',
        'submission_digest':'b'*64,'evaluator_fingerprint':'c'*64,'test_suite_fingerprint':'d'*64,
        'verifier_identity':'EXPLICIT_SYNTHETIC_TEST_FIXTURE'})
    life.repo.put_edge('HAS_SOURCE_VERIFICATION','Candidate',cid,'SourceVerification',s['id'])
    move(life,cid,'ADMITTED_BOUNDED','admit',{'source_id':s['id'],'scope':body['scope'],'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'})
    return life.publish(cid,expected_head_sha256=life.inspect(cid)['head_sha256'],event_key='publish',reason='Synthetic exclusion control',grant=grant())


@pytest.mark.parametrize('value,decision',[(False,'ABSTAIN'),(None,'VERIFY'),('NOT_OBSERVED','VERIFY'),(True,'APPLY')])
def test_actual_declared_exclusion_controls_when(life,value,decision):
    p=proposal();p['inapplicable_conditions']={'worker_count_known':[False]}
    publish_scoped(life,p,{**FACTS,'worker_count_known':True})
    result=ExperienceResolver(life.repo).resolve({**FACTS,'worker_count_known':value})
    assert result['candidates'][0]['decision']==decision
    assert result['candidates'][0]['evidence_bundle']['publication_lifecycle']['inapplicable_conditions']==p['inapplicable_conditions']


def test_unrelated_declared_unknown_does_not_claim_or_block_a_proved_scope(life):
    p=proposal();p['unknown_fields']=['clock_domain']
    pub=publish_scoped(life,p,FACTS)
    result=ExperienceResolver(life.repo).resolve(FACTS)['candidates'][0]
    assert result['experience_id']==pub['experience_id'] and result['decision']=='APPLY'
    assert result['evidence_bundle']['publication_lifecycle']['unknown_fields']==['clock_domain']


def test_unknown_required_fact_still_blocks_admission(life):
    p=proposal();p['unknown_fields']=['concurrency_scope']
    from aevora.models import InvalidRecord
    with pytest.raises(InvalidRecord):publish_scoped(life,p,FACTS)
    assert life.repo.experience_ids()==[]


def test_real_withdrawal_between_selection_and_bundle_fails_closed(life):
    from aevora.models import GraphError
    p=proposal();pub=publish_scoped(life,p,FACTS)
    original=life.repo.experience_ids
    def controlled_selection():
        # Actual graph selection, then actual Host write between two read phases.
        # This scheduling hook does not replace a backend result or test answer.
        ids=original()
        cid=pub['candidate_id'];move(life,cid,'WITHDRAWN','withdraw-between-phases')
        return ids
    life.repo.experience_ids=controlled_selection
    try:
        with pytest.raises(GraphError):ExperienceResolver(life.repo).resolve(FACTS)
    finally:life.repo.experience_ids=original
    assert original()==[]
