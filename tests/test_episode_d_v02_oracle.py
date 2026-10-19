"""Oracle controls use actual disposable SQLite files, without candidate imports.

These developer controls are not evidence of a model run or crash experiment.
The separate private suite establishes actual worker/PID/FD observations.
"""
import copy
import json
import sqlite3
from contextlib import closing

import pytest
from app.service import OrderFlow
from evaluator.episode_d_v02_oracle import (
    decimal_tick, inspect_episode_d_v02_database, inspect_acknowledged_history,
    RecoveryEvidenceUnavailable, require_recovery_evidence, inspect_publication_boundary,
)

_SCHEMA=(
    """CREATE TABLE requests(request_id TEXT PRIMARY KEY NOT NULL,order_id TEXT NOT NULL,
    sku TEXT NOT NULL REFERENCES inventory(sku),quantity INTEGER NOT NULL CHECK(quantity>0),
    status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED','CANCELLED')),
    current_token TEXT,deadline TEXT,receipt_json TEXT)""",
    """CREATE TABLE request_claims(token TEXT PRIMARY KEY NOT NULL,
    request_id TEXT NOT NULL REFERENCES requests(request_id),order_id TEXT NOT NULL,
    sku TEXT NOT NULL REFERENCES inventory(sku),quantity INTEGER NOT NULL CHECK(quantity>0),
    issued_tick TEXT NOT NULL,issued_deadline TEXT NOT NULL)""",
)


@pytest.fixture
def stored(tmp_path):
    path=tmp_path/'business.sqlite'
    flow=OrderFlow(path)
    flow.initialize({'alpha':10,'beta':7})
    with sqlite3.connect(path) as connection:
        for sql in _SCHEMA:
            connection.execute(sql)
        connection.execute("INSERT INTO requests VALUES('r','o','alpha',2,'PENDING','t','110',NULL)")
        connection.execute("INSERT INTO request_claims VALUES('t','r','o','alpha',2,'100','110')")
    return path,flow


def audit(path,**kwargs):
    return inspect_episode_d_v02_database(path,expected_stock={'alpha':10,'beta':7},data_dir=path.parent,**kwargs)


def write(path,sql,params=()):
    with sqlite3.connect(path) as connection:
        connection.execute(sql,params)


def receipt(outcome='COMPLETE_RESERVED',**extra):
    return {'outcome':outcome,'request_id':'r','order_id':'o','sku':'alpha','quantity':2,**extra}


def terminal(path,flow,*,cancel_order=False,tombstone=False):
    flow.create_order('o','alpha',2)
    if cancel_order:
        flow.cancel_order('o')
    write(path,"UPDATE requests SET status='COMPLETED',receipt_json=?,current_token=?,deadline=? WHERE request_id='r'",
          (json.dumps(receipt()),'t' if tombstone else None,'110' if tombstone else None))


def test_raw_request_oracle_valid_and_readonly(stored):
    path,_=stored
    before=path.read_bytes()
    result=audit(path)
    assert result['consistent'],result['violations']
    assert len(result['requests'])==len(result['request_claims'])==1
    assert all(p['rejected'] for p in result['request_constraint_probes'])
    assert path.read_bytes()==before


@pytest.mark.parametrize('value',['00','01','-1','1.0','1e9',' 1',1,True,None])
def test_canonical_decimal_rejects_invalid_tick(value):
    with pytest.raises(ValueError):
        decimal_tick(value)


def test_unbounded_decimal_deadline_and_renewed_history_are_valid(stored):
    path,_=stored
    write(path,"UPDATE requests SET deadline=?",(str(100+2**80),))
    result=audit(path)
    assert result['consistent'],result['violations']
    assert decimal_tick(result['requests'][0]['deadline'])>2**63
    assert result['request_claims'][0]['issued_deadline']=='110'


@pytest.mark.parametrize('cancel_order,tombstone',[(False,False),(True,False),(False,True),(True,True)])
def test_historical_reserved_receipt_and_terminal_tombstones_are_legal(stored,cancel_order,tombstone):
    path,flow=stored
    terminal(path,flow,cancel_order=cancel_order,tombstone=tombstone)
    result=audit(path)
    assert result['consistent'],result['violations']


def test_multiple_intents_can_share_one_order(stored):
    path,flow=stored
    terminal(path,flow)
    other={**receipt(),'request_id':'other'}
    write(path,"INSERT INTO requests VALUES('other','o','alpha',2,'COMPLETED',NULL,NULL,?)",(json.dumps(other),))
    result=audit(path)
    assert result['consistent'],result['violations']
    assert len(result['orders'])==1 and len(result['requests'])==2


@pytest.mark.parametrize('sql,params,fragment',[
    ("UPDATE request_claims SET order_id='another'",(), 'Claim history payload differs'),
    ("UPDATE requests SET current_token='missing'",(), 'no corresponding claim history'),
    ("UPDATE requests SET deadline='109'",(), 'precedes issuance'),
    ("UPDATE requests SET deadline='010'",(), 'Malformed current deadline'),
    ("UPDATE request_claims SET issued_deadline='100'",(), 'does not follow issue'),
    ("UPDATE requests SET status='COMPLETED',receipt_json=?",(json.dumps(receipt()),), 'no matching persisted order'),
    ("UPDATE requests SET receipt_json='{}'",(), 'Pending request contains'),
])
def test_actual_storage_inconsistency_is_rejected(stored,sql,params,fragment):
    path,_=stored
    write(path,sql,params)
    result=audit(path)
    assert not result['consistent']
    assert any(fragment in text for text in result['violations']),result


@pytest.mark.parametrize('value',[
    '{}','[]','null','{"outcome":"REQUEST_CANCELLED","request_id":"r","order_id":"o","sku":"alpha","quantity":true}',
    '{"outcome":"REQUEST_CANCELLED","request_id":"r","request_id":"other","order_id":"o","sku":"alpha","quantity":2}',
    '{"outcome":"REQUEST_CANCELLED","request_id":"r","order_id":"o","sku":"alpha","quantity":2,"x":NaN}',
])
def test_terminal_receipt_cannot_fake_valid_json_payload(stored,value):
    path,_=stored
    write(path,"UPDATE requests SET status='CANCELLED',receipt_json=?,current_token=NULL,deadline=NULL",(value,))
    result=audit(path)
    assert not result['consistent']
    assert any('Invalid terminal receipt' in text for text in result['violations'])


def test_cancelled_intent_does_not_forbid_independent_existing_order(stored):
    path,flow=stored
    flow.create_order('o','alpha',2)
    write(path,"UPDATE requests SET status='CANCELLED',receipt_json=?,current_token=NULL,deadline=NULL",(json.dumps(receipt('REQUEST_CANCELLED')),))
    result=audit(path)
    assert result['consistent'],result['violations']


def test_cancelled_discovery_retains_legitimate_reserve_release_ledger(stored):
    path,flow=stored
    flow.create_order('o','alpha',2)
    flow.cancel_order('o')
    write(path,"UPDATE requests SET status='COMPLETED',receipt_json=?,current_token=NULL,deadline=NULL",
          (json.dumps(receipt('COMPLETE_DISCOVERED_CANCELLED')),))
    result=audit(path)
    assert result['consistent'],result['violations']
    assert len(result['ledger'])==2


def test_ack_history_rejects_terminal_mutation_even_if_current_snapshot_valid(stored):
    path,flow=stored
    terminal(path,flow)
    first=audit(path)
    write(path,"UPDATE requests SET receipt_json=?",(json.dumps(receipt(note='changed')),))
    second=audit(path)
    assert first['consistent'] and second['consistent']
    result=inspect_acknowledged_history([{'audit':first},{'audit':second}])
    assert not result['consistent']
    assert any('terminal state/receipt mutated' in text for text in result['violations'])


def test_ack_history_rejects_rewritten_issuance_even_if_current_snapshot_valid(stored):
    path,_=stored
    first=audit(path)
    write(path,"UPDATE request_claims SET issued_deadline='111'")
    write(path,"UPDATE requests SET deadline='111'")
    second=audit(path)
    assert first['consistent'] and second['consistent']
    result=inspect_acknowledged_history([{'audit':first},{'audit':second}])
    assert not result['consistent']
    assert any('Issuance history disappeared or mutated' in text for text in result['violations'])


def test_host_expected_identity_and_absent_request_are_enforced(stored):
    path,_=stored
    result=audit(path,expected_identity=(0,0))
    assert not result['consistent']
    assert any('inode differs' in text for text in result['violations'])
    result=audit(path,expected_requests={'r':None})
    assert not result['consistent']


def test_view_cannot_replace_public_base_table(stored):
    path,_=stored
    write(path,'ALTER TABLE requests RENAME TO secret_requests')
    write(path,'CREATE VIEW requests AS SELECT * FROM secret_requests')
    result=audit(path)
    assert not result['consistent']
    assert any('Missing public base table' in text for text in result['violations'])


def test_missing_observation_is_explicit_infrastructure_error():
    with pytest.raises(RecoveryEvidenceUnavailable,match='RECOVERY_EVIDENCE_UNVERIFIED'):
        require_recovery_evidence({}, {},method='claim_request',label='transaction_committed')



def test_terminal_extra_field_types_cannot_mutate_through_python_equality(stored):
    path,flow=stored
    terminal(path,flow)
    write(path,"UPDATE requests SET receipt_json=?",(json.dumps(receipt(note=1)),))
    first=audit(path)
    write(path,"UPDATE requests SET receipt_json=?",(json.dumps(receipt(note=True)),))
    second=audit(path)
    assert first['consistent'] and second['consistent']
    assert not inspect_acknowledged_history([{'audit':first},{'audit':second}])['consistent']


def test_ignore_duplicate_primary_key_is_valid_constraint_enforcement(stored):
    path,_=stored
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER ignore_duplicate_request BEFORE INSERT ON requests "
                           "WHEN EXISTS(SELECT 1 FROM requests WHERE request_id=NEW.request_id) "
                           "BEGIN SELECT RAISE(IGNORE); END")
    result=audit(path)
    assert result['consistent'],result['violations']
    assert all(item.get('rejected',True) for item in result['request_constraint_probes'])



@pytest.mark.parametrize('readonly,method,label',[(1,'complete_request','before_response'),(True,'claim_request','before_response'),(True,'complete_request','before_commit')])
def test_readonly_exception_is_typed_and_limited_to_stale_response(readonly,method,label):
    with pytest.raises(RecoveryEvidenceUnavailable,match='invalid readonly stale evidence scope'):
        require_recovery_evidence({}, {},method=method,label=label,readonly_stale=readonly)



def test_split_committed_business_without_receipt_is_detected_from_actual_sqlite(stored):
    path,flow=stored
    before=audit(path)
    # Actual first business transaction, simulating a bad split publication.
    # Both individual snapshots conserve inventory; only the trusted previous
    # claim ACK establishes that this order did not predate the complete call.
    flow.create_order('o','alpha',2)
    partial=audit(path)
    assert before['consistent'] and partial['consistent']
    boundary=inspect_publication_boundary(before,partial,request_id='r')
    assert not boundary['consistent'] and boundary['applicable']
    assert 'without terminal request receipt' in boundary['violations'][0]
    terminal(path,flow)
    after=audit(path)
    assert inspect_publication_boundary(before,after,request_id='r')['consistent']


def test_existing_order_is_not_misclassified_as_new_partial_publication(stored):
    path,flow=stored
    flow.create_order('o','alpha',2)
    before=audit(path)
    flow.reserve_inventory('o')
    after=audit(path)
    boundary=inspect_publication_boundary(before,after,request_id='r')
    assert boundary['consistent'] and not boundary['applicable']


def test_existing_unreserved_order_new_reserve_requires_atomic_terminal_receipt(stored):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    before=audit(path)
    flow.reserve_inventory('o')
    partial=audit(path)
    assert before['consistent'] and partial['consistent']
    boundary=inspect_publication_boundary(before,partial,request_id='r')
    assert boundary['applicable'] and boundary['business_effect_observed']
    assert boundary['publication_kind']=='EXISTING_UNRESERVED_ORDER'
    assert not boundary['consistent']
    assert 'without terminal request receipt' in boundary['violations'][0]
    terminal(path,flow)
    after=audit(path)
    assert inspect_publication_boundary(before,after,request_id='r')['consistent']


def test_existing_unreserved_order_audit_only_first_commit_may_remain_pending(stored):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    before=audit(path)
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE operation_audit(note TEXT)')
        connection.execute("INSERT INTO operation_audit VALUES('complete entered')")
    after=audit(path)
    boundary=inspect_publication_boundary(before,after,request_id='r')
    assert boundary['applicable'] and boundary['consistent']
    assert not boundary['business_effect_observed']
    assert after['requests'][0]['status']=='PENDING'


def test_unrelated_order_reservation_is_not_attributed_to_existing_target(stored):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    flow.create_order('unrelated','beta',3,reserve=False)
    before=audit(path)
    flow.reserve_inventory('unrelated')
    after=audit(path)
    boundary=inspect_publication_boundary(before,after,request_id='r')
    assert boundary['consistent'] and not boundary['business_effect_observed']


def test_historical_other_request_and_cancelled_order_are_not_new_publication(stored):
    path,flow=stored
    terminal(path,flow,cancel_order=True)
    write(path,"INSERT INTO requests VALUES('other','o','alpha',2,'PENDING',NULL,NULL,NULL)")
    before=audit(path)
    after=audit(path)
    assert before['consistent'] and after['consistent']
    boundary=inspect_publication_boundary(before,after,request_id='other')
    assert boundary['consistent'] and not boundary['applicable']


def test_new_business_requires_typed_complete_reserved_receipt(stored):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    before=audit(path)
    flow.reserve_inventory('o')
    write(path,"UPDATE requests SET status='COMPLETED',current_token=NULL,deadline=NULL,receipt_json=?",
          (json.dumps(receipt()),))
    after=audit(path)
    assert inspect_publication_boundary(before,after,request_id='r')['consistent']
    # Protocol-negative projections exercise this function's own typed guard.
    # The raw DB Oracle separately refuses malformed persisted receipt values.
    for value in (True,2.0):
        projected=copy.deepcopy(after)
        projected['requests'][0]['receipt']['quantity']=value
        assert not inspect_publication_boundary(before,projected,request_id='r')['consistent']


def test_existing_unreserved_order_cannot_disappear_before_complete_publication(stored):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    before=audit(path)
    write(path,"DELETE FROM orders WHERE order_id='o'")
    after=audit(path)
    assert before['consistent'] and after['consistent']
    assert after['orders']==after['ledger']==[]
    boundary=inspect_publication_boundary(before,after,request_id='r')
    assert not boundary['consistent'] and boundary['applicable']
    assert any('order disappeared' in item for item in boundary['violations'])


@pytest.mark.parametrize('field,value',[('sku','beta'),('quantity',3)])
def test_existing_unreserved_order_cannot_rewrite_acknowledged_typed_payload(stored,field,value):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    before=audit(path)
    # Actual ordinary SQLite UPDATE/COMMIT, not a fabricated Oracle result.
    write(path,'UPDATE orders SET '+field+"=? WHERE order_id='o'",(value,))
    after=audit(path)
    assert before['consistent'] and after['consistent']
    boundary=inspect_publication_boundary(before,after,request_id='r')
    assert not boundary['consistent'] and boundary['applicable']
    assert any('changed typed payload' in item for item in boundary['violations'])


def test_existing_unreserved_order_cannot_cancel_in_sole_complete_window(stored):
    path,flow=stored
    flow.create_order('o','alpha',2,reserve=False)
    before=audit(path)
    # Valid legacy cancel is an invalid effect of this sole complete call.
    # An actual independent concurrent cancel is outside this helper's scope.
    flow.cancel_order('o')
    after=audit(path)
    assert before['consistent'] and after['consistent']
    boundary=inspect_publication_boundary(before,after,request_id='r')
    assert not boundary['consistent'] and boundary['applicable']
    assert any('changed lifecycle' in item for item in boundary['violations'])
