"""Actual process death at observed SQLite writes and lost response boundaries."""
import pytest
from .test_requests import assert_truth, assert_receipt, request_row
from evaluator.episode_d_v02_oracle import inspect_publication_boundary

_CASES=[(method,label) for method in ("claim_request","complete_request")
        for label in ("before_commit","transaction_committed","before_response")]


@pytest.mark.parametrize("interrupted",_CASES,indirect=True,
                         ids=[method+"-"+label for method,label in _CASES])
def test_observed_crash_recovery_and_identical_retry(interrupted):
    case=interrupted
    client=case["client"]
    pool=client.pool
    before=case["before"]
    assert_truth(before)
    assert case["proof"]["verified"] is True
    assert_truth(case["before_call"])
    if case["method"] == "complete_request":
        boundary = inspect_publication_boundary(case["before_call"], before, request_id="lost")
        client.save("oracle", case["method"] + "-" + case["label"] + "-publication-boundary", boundary)
        assert boundary["consistent"], boundary["violations"]
    if case["method"]=="claim_request":
        # The exact repeated request may return BUSY after committed unknown
        # ack. Never manufacture its missing token: use the public deadline to
        # expire it and issue a new opaque grant through the ordinary API.
        result=pool.call(1,"claim_request",**case["params"])
        if result["outcome"]=="CLAIM_BUSY":
            pool.clock.advance_to(result["request"]["deadline"])
            result=pool.call(1,"claim_request",**case["params"])
        assert result["outcome"]=="CLAIM_GRANTED"
        handle=result["handle"]
    else:
        handle=case["handle"]
        result=pool.call(1,"complete_request",handle=handle)
        assert_receipt(result,outcome="COMPLETE_RESERVED",request_id="lost",order_id="lost-order",quantity=3)
    receipt=pool.call(0,"complete_request",handle=handle)
    assert_receipt(receipt,outcome="COMPLETE_RESERVED",request_id="lost",order_id="lost-order",quantity=3)
    assert pool.call(1,"complete_request",handle=handle)==receipt
    after=client.oracle(case["method"]+"-"+case["label"]+"-after-retry")
    assert_truth(after)
    assert len(after["orders"])==len(after["ledger"])==1
    assert after["inventory"][0]["reserved"]==3 and after["inventory"][0]["available"]==7
    assert request_row(after,"lost")["receipt"]==receipt
    # Committed-before-ACK need not be a specific private SQL transaction.
    # A successful before_response, however, proves the public operation had
    # completed before the transport response was withheld.
    if case["label"]=="before_response":
        assert case["crash"]["event"]["metadata"]["ok"] is True
        if case["method"]=="complete_request":
            assert request_row(before,"lost")["status"]=="COMPLETED"
            assert before["inventory"][0]["reserved"]==3
        else:
            assert request_row(before,"lost")["status"]=="PENDING"
            assert before["orders"]==before["ledger"]==[]



def test_stale_cleanup_response_lost_restart_does_not_erase_current_owner(stale_interrupted):
    case=stale_interrupted
    client=case["client"]
    pool=client.pool
    assert_truth(case["before"])
    assert_truth(case["recovered"])
    current=request_row(case["recovered"])
    assert current["status"]=="PENDING"
    assert current["current_token"]==case["new"]["handle"]["token"]
    assert current["deadline"]==str(case["new"]["request"]["deadline"])
    assert case["recovered"]["orders"]==case["recovered"]["ledger"]==[]
    result=pool.call(0,"complete_request",handle=case["old"])
    late=client.oracle("stale-lost-ack-identical-retry",stop=False,expected_orders={"o":None},
                      expected_requests={"r":{"current_token":case["new"]["handle"]["token"],"deadline":current["deadline"]}})
    assert_truth(late)
    assert result["outcome"]=="STALE_HANDLE",result
    receipt=pool.call(1,"complete_request",handle=case["new"]["handle"])
    assert_receipt(receipt,outcome="COMPLETE_RESERVED")
    assert_truth(client.oracle("stale-lost-ack-new-owner"))


def test_existing_unreserved_order_crash_publication_is_atomic(existing_unreserved_interrupted):
    case = existing_unreserved_interrupted
    client, pool = case["client"], case["client"].pool
    before, recovered = case["before_call"], case["recovered"]
    assert_truth(before)
    assert_truth(recovered)
    assert case["proof"]["verified"] is True
    prior_order = next(row for row in before["orders"] if row["order_id"] == "existing-order")
    assert prior_order["status"] == "created" and prior_order["reservation_state"] == "none"
    assert (prior_order["sku"], prior_order["quantity"]) == ("SKU-1", 3)
    assert not any(row["order_id"] == "existing-order" and row["action"] == "reserve" for row in before["ledger"])
    assert request_row(before, "existing")["status"] == "PENDING"
    assert request_row(before, "existing")["receipt"] is None
    boundary = inspect_publication_boundary(before, recovered, request_id="existing")
    client.save("oracle", "existing-unreserved-publication-boundary", boundary)
    assert boundary["applicable"] and boundary["publication_kind"] == "EXISTING_UNRESERVED_ORDER"
    assert boundary["consistent"], boundary["violations"]
    # An audit-only first commit is legal: no transaction count or premature
    # COMPLETED requirement applies until this sole call creates a new effect.
    receipt = pool.call(1, "complete_request", handle=case["handle"])
    assert_receipt(receipt, outcome="COMPLETE_RESERVED", request_id="existing", order_id="existing-order", quantity=3)
    assert pool.call(0, "complete_request", handle=case["handle"]) == receipt
    after = client.oracle("existing-unreserved-identical-retry")
    assert_truth(after)
    assert len(after["orders"]) == len(after["ledger"]) == 1
    assert after["inventory"][0]["reserved"] == 3 and after["inventory"][0]["available"] == 7
    assert request_row(after, "existing")["receipt"] == receipt
