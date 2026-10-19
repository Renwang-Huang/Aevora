"""Acknowledged cross-process lease histories, without transaction barriers."""
import pytest
from .test_requests import assert_truth, assert_receipt, request_row


def assert_stale_or_terminal(result, terminal=None):
    assert isinstance(result,dict)
    assert result.get("outcome")=="STALE_HANDLE" or terminal is not None and result==terminal,result


def test_deadline_equality_rejects_publication(client):
    pool=client.initialize({"SKU-1":5})
    old=client.claim(ttl=10)["handle"]
    pool.clock.advance(10)
    result=pool.call(1,"complete_request",handle=old)
    audit=client.oracle("expired-publication",expected_orders={"o":None})
    assert_truth(audit)
    assert_stale_or_terminal(result)
    assert request_row(audit)["status"]=="PENDING"


@pytest.mark.parametrize("wal",[False,True],ids=["delete","wal"])
def test_paused_holder_cannot_publish_after_takeover_ack(client,wal):
    pool=client.initialize({"SKU-1":8},2,wal=wal)
    first=client.claim(0,quantity=2)["handle"]
    pool.pause(0)
    pool.clock.advance(10)
    current=client.claim(1,quantity=2)
    assert current["outcome"]=="CLAIM_GRANTED" and current["handle"]!=first
    takeover=client.oracle("takeover-ack",stop=False)
    assert_truth(takeover)
    pool.resume(0)
    result=pool.call(0,"complete_request",handle=first)
    late=client.oracle("late-old-publication",stop=False,expected_orders={"o":None},
                        expected_requests={"r":{"status":"PENDING","current_token":current["handle"]["token"]}})
    assert_truth(late)
    assert_stale_or_terminal(result)
    receipt=pool.call(1,"complete_request",handle=current["handle"])
    assert_receipt(receipt,outcome="COMPLETE_RESERVED",quantity=2)
    final=client.oracle("current-publication")
    assert_truth(final)
    assert len(final["ledger"])==1 and final["inventory"][0]["reserved"]==2


def test_cancel_ack_prevents_late_resurrection(client):
    pool=client.initialize({"SKU-1":6})
    handle=client.claim(0,quantity=2)["handle"]
    pool.pause(0)
    terminal=pool.call(1,"cancel_request",request_id="r")
    assert_receipt(terminal,outcome="REQUEST_CANCELLED",quantity=2)
    cancelled=client.oracle("cancel-ack",stop=False)
    assert_truth(cancelled)
    pool.resume(0)
    result=pool.call(0,"complete_request",handle=handle)
    late=client.oracle("late-after-cancel",expected_orders={"o":None},expected_requests={"r":{"status":"CANCELLED","receipt":terminal}})
    assert_truth(late)
    assert_stale_or_terminal(result,terminal)
    assert late["inventory"][0]["available"]==6 and not late["ledger"]


def test_stale_renewal_cannot_extend_or_replace_new_claim(client):
    pool=client.initialize({"SKU-1":6})
    old=client.claim(ttl=10)["handle"]
    pool.clock.advance(10)
    new=client.claim(1,ttl=20)
    before=client.oracle("new-claim-ack",stop=False)
    assert_truth(before)
    result=pool.call(0,"renew_request",handle=old,ttl=2**80)
    after=client.oracle("stale-renew",expected_requests={"r":{"current_token":new["handle"]["token"],"deadline":str(new["request"]["deadline"])}})
    assert_truth(after)
    assert_stale_or_terminal(result)
    assert after["request_claims"]==before["request_claims"]


def test_aba_old_claim_never_regains_authority(client):
    pool=client.initialize({"SKU-1":9})
    handles=[]
    for index in range(3):
        granted=client.claim(index%2,ttl=2)
        assert granted["outcome"]=="CLAIM_GRANTED"
        handles.append(granted["handle"])
        if index<2:
            pool.clock.advance(2)
    assert len({handle["token"] for handle in handles})==3
    assert_truth(client.oracle("third-grant-ack",stop=False))
    for index,old in enumerate(handles[:2]):
        result=pool.call(index%2,"complete_request",handle=old)
        audit=client.oracle(f"aba-old-{index}",stop=False,expected_orders={"o":None},
                            expected_requests={"r":{"current_token":handles[-1]["token"],"status":"PENDING"}})
        assert_truth(audit)
        assert_stale_or_terminal(result)
    result=pool.call(1,"complete_request",handle=handles[-1])
    assert_receipt(result,outcome="COMPLETE_RESERVED")
    assert_truth(client.oracle("aba-current"))


def test_stale_cleanup_cannot_erase_new_owner_and_restart_preserves_it(client):
    pool=client.initialize({"SKU-1":5})
    old=client.claim(ttl=1)["handle"]
    pool.clock.advance(1)
    new=client.claim(1,ttl=30)
    before=client.oracle("new-owner-ack",stop=False)
    assert_truth(before)
    result=pool.call(0,"complete_request",handle=old)
    late=client.oracle("stale-cleanup-ack",restart=True,expected_orders={"o":None},
                       expected_requests={"r":{"current_token":new["handle"]["token"],"deadline":str(new["request"]["deadline"])}})
    assert_truth(late)
    assert_stale_or_terminal(result)
    assert late["request_claims"]==before["request_claims"]
    receipt=pool.call(1,"complete_request",handle=new["handle"])
    assert_receipt(receipt,outcome="COMPLETE_RESERVED")
    assert_truth(client.oracle("new-owner-retry"))


def test_large_ttl_is_not_lexically_expired(client):
    pool=client.initialize({"SKU-1":5})
    granted=client.claim(ttl=2**80)
    assert granted["outcome"]=="CLAIM_GRANTED"
    assert granted["request"]["deadline"]==100+2**80
    pool.clock.advance(1000)
    busy=client.claim(1)
    assert busy["outcome"]=="CLAIM_BUSY"
    result=pool.call(0,"complete_request",handle=granted["handle"])
    assert_receipt(result,outcome="COMPLETE_RESERVED")
    assert_truth(client.oracle())


def test_complete_cancel_overlap_accepts_either_legal_winner(client):
    pool=client.initialize({"SKU-1":5})
    handle=client.claim(quantity=2)["handle"]
    batch=client.batch([{"method":"complete_request","params":{"handle":handle}},
                        {"method":"cancel_request","params":{"request_id":"r"}}],"complete-cancel")
    assert all(row["ok"] for row in batch["results"]),batch
    audit=client.oracle("overlap-winner")
    assert_truth(audit)
    row=request_row(audit)
    completion,cancellation=[item["result"] for item in batch["results"]]
    if row["status"]=="COMPLETED":
        assert_receipt(completion,outcome="COMPLETE_RESERVED",quantity=2)
        assert cancellation=={"outcome":"ALREADY_COMPLETED","request_id":"r","receipt":completion}
        assert len(audit["orders"])==len(audit["ledger"])==1
    else:
        assert row["status"]=="CANCELLED"
        assert_receipt(cancellation,outcome="REQUEST_CANCELLED",quantity=2)
        assert_stale_or_terminal(completion,cancellation)
        assert not audit["orders"] and not audit["ledger"]


def test_unexpired_renewal_blocks_takeover_until_new_deadline(client):
    pool=client.initialize({"SKU-1":5})
    granted=client.claim(ttl=2)
    pool.clock.advance(1)
    renewed=pool.call(0,"renew_request",handle=granted["handle"],ttl=30)
    assert renewed["outcome"]=="CLAIM_RENEWED"
    pool.clock.advance(1)
    assert client.claim(1)["outcome"]=="CLAIM_BUSY"
    pool.clock.advance_to(renewed["request"]["deadline"])
    new=client.claim(1)
    assert new["outcome"]=="CLAIM_GRANTED" and new["handle"]!=granted["handle"]
    assert_truth(client.oracle())


def test_commit_crossing_deadline_is_judged_by_legal_call_interval(crossed_deadline):
    result=crossed_deadline["result"]
    # There was no competing writer or authority takeover. A successful
    # publication authorized earlier in this call is legitimate; an equivalent
    # strategy may recheck time and reject with no side effects.
    audit=crossed_deadline["audit"]
    assert_truth(audit)
    if result.get("outcome")=="COMPLETE_RESERVED":
        assert_receipt(result,outcome="COMPLETE_RESERVED")
        assert request_row(audit)["status"]=="COMPLETED"
        assert len(audit["ledger"])==1
    else:
        assert_stale_or_terminal(result)
        assert not audit["orders"] and not audit["ledger"]
        assert request_row(audit)["status"]=="PENDING"
