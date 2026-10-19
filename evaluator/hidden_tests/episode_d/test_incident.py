"""Engineering invariants, independent of the chosen repair mechanism."""
import pytest
from evaluator.rpc import RemoteBusinessError

TEST_SUITE_VERSION = "1.2.0"


def requests(count, quantity=1, *, prefix="purchase", sku="SKU-1"):
    return [{"method": "create_order", "params": {"order_id": f"{prefix}-{i}", "sku": sku,
             "quantity": quantity}} for i in range(count)]


def assert_truth(oracle):
    assert oracle["consistent"], oracle["violations"]


def assert_topology(batch, workers):
    results = batch["results"]
    assert len({r["host_pid"] for r in results}) == workers
    assert {r["worker_index"] for r in results} == set(range(workers))
    assert len({identity["host_pid"] for identity in batch["execution"]["worker_identities"]}) == workers
    assert batch["execution"]["shared_database"]["availability"] == "AVAILABLE"
    assert batch["execution"]["shared_database"]["links"] == 1
    # Recorded trusted dispatch intervals prove overlapping in-flight requests.
    assert any(a["host_pid"] != b["host_pid"] and max(a["start_ns"], b["start_ns"]) < min(a["end_ns"], b["end_ns"])
               for a in results for b in results)


def assert_purchases(batch, oracle, traffic, stock, quantity=1, *, workers=2):
    assert_topology(batch, workers)
    assert len(batch["results"]) == len(traffic)
    assert {r["index"] for r in batch["results"]} == set(range(len(traffic)))
    accepted = [r for r in batch["results"] if r["ok"]]
    rejected = [r for r in batch["results"] if not r["ok"]]
    expected = min(len(traffic), stock // quantity)
    assert len(accepted) == expected, batch
    assert len(rejected) == len(traffic) - expected
    assert all(r["error"]["type"] == "InsufficientInventory" for r in rejected), rejected
    ids = {traffic[r["index"]]["params"]["order_id"] for r in accepted}
    assert all(r["result"]["order_id"] == traffic[r["index"]]["params"]["order_id"] and
               r["result"]["status"] == "reserved" and r["result"]["reservation_state"] == "active" for r in accepted)
    assert_truth(oracle)
    assert {o["order_id"] for o in oracle["orders"]} == ids
    assert {l["order_id"] for l in oracle["ledger"]} == ids
    row = oracle["inventory"][0]
    assert row["available"] == stock - expected * quantity
    assert row["reserved"] == expected * quantity


def test_single_worker_normal_business(client):
    # Independent workers, but diagnostic requests serialized to one worker.
    pool = client.initialize({"SKU-1": 7}, 2)
    for i in range(7):
        assert pool.call(0, "create_order", order_id=f"single-{i}", sku="SKU-1", quantity=1)["status"] == "reserved"
    with pytest.raises(RemoteBusinessError, match="InsufficientInventory"):
        pool.call(0, "create_order", order_id="insufficient", sku="SKU-1", quantity=1)
    oracle = client.oracle()
    assert_truth(oracle)
    assert len(oracle["orders"]) == len(oracle["ledger"]) == 7


@pytest.mark.parametrize("workers", [2, 4], ids=["workers2", "workers4"])
def test_all_workers_persist_valid_writes(client, workers):
    client.initialize({"SKU-1": 100}, workers)
    traffic = requests(workers * 3, prefix="witness")
    batch = client.batch(traffic)
    oracle = client.oracle(requests=traffic, results=batch["results"], required_workers=list(range(workers)))
    assert_purchases(batch, oracle, traffic, 100, workers=workers)
    assert {r["worker_index"] for r in batch["results"] if r["ok"]} == set(range(workers))


@pytest.mark.parametrize("workers", [2, 4], ids=["workers2", "workers4"])
def test_concurrent_capacity_and_exhaustion(client, workers):
    client.initialize({"SKU-1": 50}, workers)
    traffic = requests(200)
    batch = client.batch(traffic)
    oracle = client.oracle(requests=traffic, results=batch["results"])
    assert_purchases(batch, oracle, traffic, 50, workers=workers)


@pytest.mark.parametrize("stock,count,quantity,workers", [(1,24,1,4), (7,32,1,2), (17,32,3,4), (0,16,1,2)],
                         ids=["last-item", "stock7", "quantity3", "stock0"])
def test_scaled_inventory_invariants(client, stock, count, quantity, workers):
    client.initialize({"SKU-1": stock}, workers)
    traffic = requests(count, quantity)
    batch = client.batch(traffic)
    oracle = client.oracle(requests=traffic, results=batch["results"])
    assert_purchases(batch, oracle, traffic, stock, quantity, workers=workers)


@pytest.mark.parametrize("workers", [2,4], ids=["workers2", "workers4"])
def test_identical_order_retry_is_one_persistent_reservation(client, workers):
    client.initialize({"SKU-1": 13}, workers)
    traffic = [{"method":"create_order", "params":{"order_id":"same-order", "sku":"SKU-1", "quantity":3}}
               for _ in range(workers * 3)]
    batch = client.batch(traffic)
    oracle = client.oracle(requests=traffic, results=batch["results"])
    assert_topology(batch, workers)
    assert all(r["ok"] and r["result"]["order_id"] == "same-order" for r in batch["results"])
    assert_truth(oracle)
    assert len(oracle["orders"]) == len(oracle["ledger"]) == 1
    assert oracle["inventory"][0]["available"] == 10


def test_conflicting_order_payload_remains_business_error(client):
    pool = client.initialize({"SKU-1":10,"SKU-2":9},4)
    pool.call(0,"create_order",order_id="conflict",sku="SKU-1",quantity=2)
    for worker in range(4):
        with pytest.raises(RemoteBusinessError,match="OrderConflict"):
            pool.call(worker,"create_order",order_id="conflict",sku="SKU-2",quantity=1)
    oracle=client.oracle()
    assert_truth(oracle)
    assert len(oracle["orders"]) == len(oracle["ledger"]) == 1


def test_cross_worker_cancel_release_and_cancelled_retry(client):
    pool=client.initialize({"SKU-1":10},4)
    pool.call(0,"create_order",order_id="cancel",sku="SKU-1",quantity=3)
    pool.call(1,"cancel_order",order_id="cancel")
    pool.call(2,"cancel_order",order_id="cancel")
    pool.call(3,"release_inventory",order_id="cancel")
    assert pool.call(0,"create_order",order_id="cancel",sku="SKU-1",quantity=3)["status"] == "cancelled"
    oracle=client.oracle()
    assert_truth(oracle)
    assert oracle["inventory"][0]["available"]==10
    assert sorted(l["action"] for l in oracle["ledger"])==["release","reserve"]


def test_separate_create_and_reserve_idempotence(client):
    pool=client.initialize({"SKU-1":10},2)
    pool.call(0,"create_order",order_id="separate",sku="SKU-1",quantity=3,reserve=False)
    for worker in (1,0,1):
        pool.call(worker,"reserve_inventory",order_id="separate")
    oracle=client.oracle()
    assert_truth(oracle)
    assert oracle["inventory"][0]["reserved"]==3
    assert len(oracle["ledger"])==1


def test_invalid_inputs_and_insufficient_rollback(client):
    client.initialize({"SKU-1":7},4)
    traffic=requests(8,prefix="valid")
    traffic += [{"method":"create_order","params":{"order_id":f"invalid-{i}","sku":"SKU-1","quantity":v}}
                for i,v in enumerate([0,-1,True,1.5,"1"])]
    batch=client.batch(traffic)
    oracle=client.oracle(requests=traffic,results=batch["results"])
    assert_topology(batch,4)
    assert_truth(oracle)
    for r in batch["results"]:
        if r["index"]>=8:
            assert not r["ok"] and r["error"]["type"]=="InvalidInput"
    assert len([r for r in batch["results"] if r["ok"]])==7
    assert len(oracle["orders"])==len(oracle["ledger"])==7


def test_independent_skus_share_no_reservations(client):
    client.initialize({"SKU-1":6,"SKU-2":9},4)
    traffic=requests(30,prefix="first")+requests(30,prefix="second",sku="SKU-2")
    batch=client.batch(traffic)
    oracle=client.oracle(requests=traffic,results=batch["results"])
    assert_topology(batch,4)
    assert_truth(oracle)
    assert sum(r["ok"] for r in batch["results"])==15
    for row in oracle["inventory"]:
        assert row["available"]==0
        assert row["reserved"]==client.stock[row["sku"]]
    assert all(r["ok"] or r["error"]["type"]=="InsufficientInventory" for r in batch["results"])


def test_mixed_cancellations_and_purchases_share_consistent_state(client):
    pool=client.initialize({"SKU-1":20},4)
    for i in range(4):
        pool.call(i,"create_order",order_id=f"prior-{i}",sku="SKU-1",quantity=2)
    traffic=[{"method":"cancel_order","params":{"order_id":f"prior-{i}"}} for i in range(4)]
    traffic += requests(8,prefix="replacement")
    batch=client.batch(traffic)
    oracle=client.oracle(requests=traffic,results=batch["results"])
    assert_topology(batch,4)
    assert all(r["ok"] for r in batch["results"])
    assert_truth(oracle)
    assert len(oracle["orders"])==12
    assert len(oracle["ledger"])==16
    assert oracle["inventory"][0]["available"]==12
    assert oracle["inventory"][0]["reserved"]==8


@pytest.mark.parametrize("workers",[2,4],ids=["workers2","workers4"])
def test_wal_shared_database(client,workers):
    client.initialize({"SKU-1":23},workers,wal=True)
    traffic=requests(60)
    batch=client.batch(traffic)
    oracle=client.oracle(requests=traffic,results=batch["results"])
    assert_purchases(batch,oracle,traffic,23,workers=workers)


def test_reset_and_independent_reexecution(client):
    for round_number in range(2):
        client.initialize({"SKU-1":5},2)
        traffic=requests(20,prefix=f"reset-{round_number}")
        batch=client.batch(traffic,label=f"round-{round_number}")
        oracle=client.oracle(label=f"round-{round_number}",requests=traffic,results=batch["results"])
        assert_purchases(batch,oracle,traffic,5)


def test_uncoordinated_requests_still_obey_capacity(client):
    client.initialize({"SKU-1":11},4)
    traffic=requests(40)
    batch=client.batch(traffic,controlled=False)
    oracle=client.oracle(requests=traffic,results=batch["results"])
    assert_purchases(batch,oracle,traffic,11,workers=4)


@pytest.mark.parametrize("point",["before_commit","transaction_committed","before_response"],
                         ids=["uncommitted","committed","response-lost"])
def test_worker_interruption_restart_and_retry(client,point):
    pool=client.initialize({"SKU-1":10},4)
    crash=pool.crash_call(0,"create_order",point,order_id="interrupted",sku="SKU-1",quantity=3)
    client.save("recovery",point,crash)
    # Observe actual SQLite boundaries rather than a chosen persistence helper.
    # Unsupported observation is explicitly UNVERIFIED in recovery_coverage;
    # absence alone does not turn a legal strategy into a business failure.
    if point=="before_response":
        assert crash["availability"]=="AVAILABLE",crash
        assert crash["event"]["metadata"]["ok"] is True, crash
    if crash["availability"]=="AVAILABLE":
        assert crash["request_outcome"]["ok"] is False
        assert crash["request_outcome"]["error"]["type"] == "RemoteExecutionError",crash
        assert crash["kill"]["signal"]=="SIGKILL"
    oracle=client.oracle(label=point+"-before-retry",recover=True,restart=True)
    assert_truth(oracle)
    before_ids={row["order_id"] for row in oracle["orders"]}
    # An unacknowledged operation may have committed a legal pending creation,
    # a complete reservation, or only auxiliary metadata. Judge persistent
    # invariants and retry semantics rather than prescribing transaction count.
    assert before_ids <= {"interrupted"}, oracle
    if before_ids:
        order = oracle["orders"][0]
        assert order["sku"] == "SKU-1" and order["quantity"] == 3
        assert (order["status"], order["reservation_state"]) in {
            ("created", "none"), ("reserved", "active")}, oracle
    if crash["availability"]=="AVAILABLE" and point=="before_response":
        assert before_ids == {"interrupted"}, oracle
        assert oracle["orders"][0]["status"] == "reserved"
        assert oracle["orders"][0]["reservation_state"] == "active"
        assert oracle["orders"][0]["quantity"] == 3
        assert len(oracle["ledger"]) == 1
        assert oracle["ledger"][0]["action"] == "reserve"
        assert oracle["inventory"][0]["available"] == 7
        assert oracle["inventory"][0]["reserved"] == 3
    pool.call(1,"create_order",order_id="interrupted",sku="SKU-1",quantity=3)
    pool.call(2,"create_order",order_id="interrupted",sku="SKU-1",quantity=3)
    pool.restart(0)
    pool.call(0,"create_order",order_id="after-restart",sku="SKU-1",quantity=1)
    final=client.oracle(label=point+"-after-retry")
    assert_truth(final)
    assert {r["order_id"] for r in final["orders"]}=={"interrupted","after-restart"}
    assert len(final["ledger"])==2
    assert final["inventory"][0]["available"]==6
    assert final["inventory"][0]["reserved"]==4
