"""Public behavior and independent inventory/intent records under real RPC."""
import pytest
from evaluator.rpc import RemoteBusinessError
from evaluator.episode_d_v02_oracle import public_request


def assert_truth(audit):
    assert audit["consistent"], audit["violations"]
    assert audit["request_records_available"] is True
    assert audit["acknowledged_history"]["consistent"], audit["acknowledged_history"]
    assert all(probe.get("rejected", True) for probe in audit["request_constraint_probes"])


def request_row(audit, identity="r"):
    return next(row for row in audit["requests"] if row["request_id"] == identity)


def assert_receipt(receipt, *, outcome, request_id="r", order_id="o", sku="SKU-1", quantity=1):
    assert isinstance(receipt, dict)
    expected = {"outcome": outcome, "request_id": request_id, "order_id": order_id, "sku": sku, "quantity": quantity}
    assert all(type(receipt.get(key)) is type(value) and receipt.get(key) == value for key, value in expected.items()), receipt


def test_claim_complete_idempotence_and_persisted_projection(client):
    pool = client.initialize({"SKU-1": 10})
    claim = client.claim(quantity=3)
    assert claim["outcome"] == "CLAIM_GRANTED"
    before = client.oracle("claim-ack", stop=False)
    assert_truth(before)
    assert before["orders"] == before["ledger"] == []
    assert before["inventory"][0]["available"] == 10
    public = pool.call(1, "get_request", request_id="r")
    assert public == public_request(request_row(before))
    assert "token" not in public and "current_token" not in public
    receipt = pool.call(0, "complete_request", handle=claim["handle"])
    assert_receipt(receipt, outcome="COMPLETE_RESERVED", quantity=3)
    assert pool.call(1, "complete_request", handle=claim["handle"]) == receipt
    assert pool.call(1, "cancel_request", request_id="r") == {
        "outcome": "ALREADY_COMPLETED", "request_id": "r", "receipt": receipt}
    after = client.oracle("completed", restart=True)
    assert_truth(after)
    assert len(after["orders"]) == len(after["ledger"]) == 1
    assert pool.call(1, "get_request", request_id="r") == public_request(request_row(after))
    assert after["inventory"][0]["reserved"] == 3


def test_busy_never_discloses_token_or_reserves(client):
    pool = client.initialize({"SKU-1": 5})
    granted = client.claim()
    busy = client.claim(1)
    assert busy["outcome"] == "CLAIM_BUSY" and "handle" not in busy
    assert granted["handle"]["token"] not in str(busy)
    assert busy["request"] == pool.call(1, "get_request", request_id="r")
    audit = client.oracle()
    assert_truth(audit)
    assert len(audit["request_claims"]) == 1 and not audit["orders"]


@pytest.mark.parametrize("field,value", [("quantity",0),("quantity",True),("ttl",0),("ttl",True)],
                         ids=["quantity-zero","quantity-bool","ttl-zero","ttl-bool"])
def test_invalid_request_inputs_do_not_create_intent(client, field, value):
    client.initialize({"SKU-1": 5})
    with pytest.raises(RemoteBusinessError) as caught:
        client.claim(**{field:value})
    assert caught.value.kind == "InvalidInput"
    audit = client.oracle()
    assert_truth(audit)
    assert audit["requests"] == audit["request_claims"] == audit["orders"] == []


def test_missing_request_and_payload_conflict_even_after_terminal(client):
    pool = client.initialize({"SKU-1": 5,"SKU-2": 5})
    for method, params in (("get_request",{"request_id":"absent"}),("cancel_request",{"request_id":"absent"}),
                           ("complete_request",{"handle":{"request_id":"absent","token":"unknown"}})):
        with pytest.raises(RemoteBusinessError) as caught:
            pool.call(1, method, **params)
        assert caught.value.kind == "RequestNotFound"
    client.claim()
    cancelled = pool.call(1,"cancel_request",request_id="r")
    assert_receipt(cancelled, outcome="REQUEST_CANCELLED")
    for params in ({"order_id":"other"},{"sku":"SKU-2"},{"quantity":2}):
        with pytest.raises(RemoteBusinessError) as caught:
            client.claim(1, **params)
        assert caught.value.kind == "RequestConflict"
    assert pool.call(0,"cancel_request",request_id="r") == cancelled
    assert_truth(client.oracle())


def test_renewal_is_monotonic_and_preserves_issuance_history_large_ttl(client):
    pool = client.initialize({"SKU-1": 5})
    original = client.claim(ttl=10)
    before = client.oracle("issued",stop=False)
    assert_truth(before)
    pool.clock.advance(2)
    renewed = pool.call(1,"renew_request",handle=original["handle"],ttl=1)
    assert renewed["outcome"] == "CLAIM_RENEWED" and renewed["handle"] == original["handle"]
    assert renewed["request"]["deadline"] >= original["request"]["deadline"]
    huge = pool.call(0,"renew_request",handle=original["handle"],ttl=2**80)
    assert huge["request"]["deadline"] >= pool.clock.tick + 2**80
    after = client.oracle("huge-deadline")
    assert_truth(after)
    assert after["request_claims"] == before["request_claims"]
    assert int(request_row(after)["deadline"]) > 2**63


def test_insufficient_inventory_releases_claim_without_order_side_effect(client):
    pool = client.initialize({"SKU-1": 4})
    pool.call(0,"create_order",order_id="block",sku="SKU-1",quantity=3)
    handle = client.claim(quantity=2)["handle"]
    insufficient = pool.call(1,"complete_request",handle=handle)
    assert_receipt(insufficient,outcome="INSUFFICIENT_INVENTORY_RETRYABLE",quantity=2)
    before = client.oracle("insufficient-ack",stop=False,expected_orders={"o":None})
    assert_truth(before)
    assert request_row(before)["status"] == "PENDING" and request_row(before)["current_token"] is None
    pool.call(0,"cancel_order",order_id="block")
    retry = client.claim(1,quantity=2)
    assert retry["outcome"] == "CLAIM_GRANTED" and retry["handle"] != handle
    receipt = pool.call(1,"complete_request",handle=retry["handle"])
    assert_receipt(receipt,outcome="COMPLETE_RESERVED",quantity=2)
    assert_truth(client.oracle())


@pytest.mark.parametrize("existing",["unreserved","cancelled-unreserved","cancelled-reserved"],ids=str)
def test_existing_matching_orders_are_preserved(client, existing):
    pool = client.initialize({"SKU-1": 7})
    pool.call(0,"create_order",order_id="o",sku="SKU-1",quantity=2,reserve=existing=="cancelled-reserved")
    if existing.startswith("cancelled"):
        pool.call(0,"cancel_order",order_id="o")
    handle = client.claim(quantity=2)["handle"]
    receipt = pool.call(1,"complete_request",handle=handle)
    expected = "COMPLETE_RESERVED" if existing == "unreserved" else "COMPLETE_DISCOVERED_CANCELLED"
    assert_receipt(receipt,outcome=expected,quantity=2)
    audit = client.oracle()
    assert_truth(audit)
    assert len(audit["orders"]) == 1
    assert audit["orders"][0]["status"] == ("reserved" if existing=="unreserved" else "cancelled")
    assert audit["inventory"][0]["available"] == (5 if existing=="unreserved" else 7)


def test_historical_receipt_survives_normal_order_cancellation(client):
    pool = client.initialize({"SKU-1": 5})
    handle = client.claim(quantity=2)["handle"]
    receipt = pool.call(0,"complete_request",handle=handle)
    assert_receipt(receipt,outcome="COMPLETE_RESERVED",quantity=2)
    assert_truth(client.oracle("receipt-ack",stop=False))
    pool.call(1,"cancel_order",order_id="o")
    assert pool.call(1,"complete_request",handle=handle) == receipt
    after = client.oracle("later-cancel")
    assert_truth(after)
    assert request_row(after)["receipt"] == receipt
    assert after["inventory"][0]["available"] == 5


def test_multiple_intents_same_order_are_legal_and_do_not_duplicate_stock(client):
    pool = client.initialize({"SKU-1": 5})
    first = client.claim(quantity=2)["handle"]
    second = client.claim(1,request_id="other-intent",quantity=2)["handle"]
    for worker, handle in ((0,first),(1,second)):
        result = pool.call(worker,"complete_request",handle=handle)
        assert_receipt(result,outcome="COMPLETE_RESERVED",request_id=handle["request_id"],quantity=2)
    third = client.claim(0,request_id="cancelled-intent",order_id="fresh")["handle"]
    pool.call(0,"cancel_request",request_id=third["request_id"])
    fourth = client.claim(1,request_id="fresh-intent",order_id="fresh")["handle"]
    pool.call(1,"complete_request",handle=fourth)
    audit = client.oracle()
    assert_truth(audit)
    assert len(audit["requests"]) == 4 and len(audit["orders"]) == len(audit["ledger"]) == 2
    assert audit["inventory"][0]["reserved"] == 3


@pytest.mark.parametrize("capacity_environment",[(2,7,2,False),(4,13,3,True)],indirect=True,ids=["two-delete","four-wal"])
def test_multiworker_capacity_and_real_write_witnesses(capacity_environment):
    prepared=capacity_environment
    client=prepared["client"]
    pool=client.pool
    workers,stock,quantity=prepared["workers"],prepared["stock"],prepared["quantity"]
    witness=prepared["witness"]
    # Each actual OS worker's durable ample-stock write and FD witness was
    # prepared in setup. Exhaustion winners need not be evenly distributed.
    assert all(row["ok"] and row["result"]["outcome"]=="COMPLETE_RESERVED" for row in witness["results"]),witness
    identities=witness["execution"]["worker_identities"]
    assert len({row["host_pid"] for row in identities})==workers
    requests=workers*4
    handles=[client.claim(i%workers,request_id=f"p{i}",order_id=f"p-order-{i}",quantity=quantity)["handle"] for i in range(requests)]
    result=client.batch([{"method":"complete_request","params":{"handle":handle}} for handle in handles],"capacity")
    assert all(row["ok"] for row in result["results"]),result
    successes=[row for row in result["results"] if row["result"]["outcome"]=="COMPLETE_RESERVED"]
    assert len(successes)==stock//quantity
    assert all(row["result"]["outcome"] in {"COMPLETE_RESERVED","INSUFFICIENT_INVENTORY_RETRYABLE"} for row in result["results"])
    audit=client.oracle()
    assert_truth(audit)
    inventory={row["sku"]:row for row in audit["inventory"]}
    assert inventory["SKU-1"]["reserved"]==(stock//quantity)*quantity
    assert inventory["SKU-1"]["available"]==stock%quantity
    assert len(audit["ledger"])==workers+stock//quantity


def test_reset_and_existing_business_regression(client):
    for cycle in range(2):
        pool=client.initialize({"SKU-1":10})
        fresh=client.oracle(f"reset-{cycle}",restart=True)
        assert_truth(fresh)
        assert fresh["requests"]==fresh["request_claims"]==fresh["orders"]==[]
        pool.call(0,"create_order",order_id="legacy",sku="SKU-1",quantity=3)
        pool.call(1,"cancel_order",order_id="legacy")
        pool.call(0,"cancel_order",order_id="legacy")
        audit=client.oracle(f"cancel-{cycle}")
        assert_truth(audit)
        assert audit["inventory"][0]["available"]==10
        assert len(audit["ledger"])==2
