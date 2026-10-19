import pytest
from aevora.contracts import *
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from tools.validation.g22_fixture import ready


def test_real_governance_withdrawal_changes_current_when_why(host):
    c,r,p=ready(host);receipt=host.publish(p)
    initial=resolve_v2(host.repo,r['facts'],'query:before',utc_now())[1][0]
    revision=next(n for n in initial[1]['nodes'].values() if n['kind']=='ExperienceRevision')
    old_values={i:digest(n) for i,n in initial[1]['nodes'].items()}
    prepared=host.govern(c['id'],r['id'],experience_id=receipt['experience_id'],target_id=revision['id'],
                         event_type='withdraw',bounded_scope=r['approved_scope'],reason='Withdraw engineering rule',request_key='withdraw-1')
    # Prepared withdrawal has no visible edges or catalogue mutation.
    assert resolve_v2(host.repo,r['facts'],'query:staged',utc_now())[1][0][0]['core_verdict']=='APPLY'
    host.publish(prepared)
    after=resolve_v2(host.repo,r['facts'],'query:after',utc_now())[1][0]
    assert after[0]['core_verdict']=='ABSTAIN' and host.head(c['id'])['state']=='WITHDRAWN'
    assert all(digest(after[1]['nodes'][i])==sha for i,sha in old_values.items())
    with pytest.raises(V2Error):
        host.transition(c['id'],'PUBLISHING',expected_head=digest(host.head(c['id'])),reason='revive')


def test_restricted_scope_changes_apply_to_abstain_and_unknown_verify(host):
    c,r,p=ready(host);receipt=host.publish(p)
    before=resolve_v2(host.repo,r['facts'],'query:before',utc_now())[1][0]
    ev=next(n for n in before[1]['nodes'].values() if n['kind']=='Evidence')
    restricted={**r['approved_scope'],'task.concurrency_scope':['multi_process']}
    p=host.govern(c['id'],r['id'],experience_id=receipt['experience_id'],target_id=ev['id'],event_type='restrict_scope',bounded_scope=restricted,reason='Evidence is valid only with independent workers',request_key='restrict')
    host.publish(p)
    after=resolve_v2(host.repo,r['facts'],'query:after',utc_now())[1][0][0]
    assert after['core_verdict'] in {'VERIFY','ABSTAIN'} and after['core_verdict']!='APPLY'


def test_cross_partition_revision_rejected_without_publication(host):
    c,r,p=ready(host);receipt=host.publish(p)
    # An arbitrary graph ID cannot move a publication between scope partitions.
    with pytest.raises(V2Error):
        host.govern(c['id'],r['id'],experience_id='Experience:foreign',target_id='ExperienceRevision:foreign',event_type='withdraw',bounded_scope=r['approved_scope'],reason='foreign partition',request_key='bad')
    assert host.repo.state()['epoch']==1


def test_explicit_revision_supersedes_old_head_in_same_final_fence(host):
    c1,r1,p1=ready(host,'old');first=host.publish(p1)
    before=resolve_v2(host.repo,r1['facts'],'query:old',utc_now())[1][0]
    oldrev=next(n for n in before[1]['nodes'].values() if n['kind']=='ExperienceRevision')
    c2,r2,p2=ready(host,'new',experience_id=first['experience_id'],supersedes=[oldrev['id']])
    assert host.head(c1['id'])['state']=='PUBLISHED'
    host.publish(p2)
    assert host.head(c1['id'])['state']=='SUPERSEDED' and host.head(c2['id'])['state']=='PUBLISHED'
    after=resolve_v2(host.repo,r2['facts'],'query:new',utc_now())[1][0]
    assert after[0]['core_verdict']=='APPLY'
    assert digest(after[1]['nodes'][oldrev['id']])==digest(oldrev)
    assert len([e for e in after[1]['edges'].values() if e['kind']=='SUPERSEDES'])==1


def test_verifier_withdrawal_updates_all_experiences_and_revokes_old_grants(host):
    c1,r1,p1=ready(host,'one');host.publish(p1)
    c2,r2,p2=ready(host,'two');host.publish(p2)
    before=resolve_v2(host.repo,r1['facts'],'query:before',utc_now())[1]
    assert len(before)==2 and all(rec['core_verdict']=='APPLY' for rec,_ in before)
    prepared=host.prepare_authority_withdrawal(host.verifier.authority_id,reason='Registered verifier source withdrawn',request_key='revoke-oracle',expected_epoch=2)
    assert all(rec['core_verdict']=='APPLY' for rec,_ in resolve_v2(host.repo,r1['facts'],'query:staged',utc_now())[1])
    receipt=host.commit_authority_withdrawal(prepared)
    assert len(receipt['affected_experience_ids'])==2 and receipt['epoch']==3 and receipt['authz_epoch']==1
    after=resolve_v2(host.repo,r1['facts'],'query:after',utc_now())[1]
    assert len(after)==2 and all(rec['core_verdict']!='APPLY' for rec,_ in after)
    assert host.repo.state()['revoked_authorities']==[host.verifier.authority_id]
    with pytest.raises(V2Error,match='UNAUTHORIZED'):host.publish(p1)
    for _,w in after:
        assert any(n['kind']=='GovernanceEvent' for n in w['nodes'].values())


def test_fresh_real_buggy_outcome_is_counterevidence_not_pass(host):
    import json,os
    from pathlib import Path
    from aevora.orderflow_outcome_bridge import TrustAnchor
    from tools.validation.g22_fixture import admitted,proposal
    cases=json.loads(Path(os.environ['AEVORA_G22_CASES']).read_text());case=cases['cases'][1]
    anchor=TrustAnchor(Path(case['root']),case['manifest_sha256'],{'evaluation_report.json':case['run_id']},profile='current_live',manifest_relative_path='HOST_RUN_MANIFEST.json',source_snapshot_relative_path='frozen_source_snapshot',source_archive_root=Path(cases['source_root']),source_manifest_sha256=cases['source_manifest_sha256'],source_manifest_relative_path='SOURCE_MANIFEST.json')
    host.verifier=host.register_orderflow(anchor,case['evaluator_sha'],case['suite_sha']);host.case=case
    p=proposal('observed-lost-update');p['strategy']='Read inventory before its write transaction and write the cached absolute quantity.'
    p['public_summary']='This Host-controlled faulty implementation produced business failure under contention.'
    c,s,o,r=admitted(host,p=p)
    assert o['verified_outcome']['verdict']=='FAIL'
    h=host.transition(c['id'],'PUBLISHING',expected_head=digest(host.head(c['id'])),reason='Publish bounded negative engineering evidence')
    prep=host.prepare(c['id'],r['id'],request_key='counter',expected_head=digest(h),expected_epoch=0)
    host.publish(prep)
    state,rows=resolve_v2(host.repo,r['facts'],'query:negative-real',utc_now())
    assert len(rows)==1 and rows[0][0]['core_verdict']=='ABSTAIN'
    assert any(e['kind']=='COUNTEREXAMPLE' for e in rows[0][1]['edges'].values())
    assert not any(e['kind']=='SUPPORTED_BY' for e in rows[0][1]['edges'].values())
