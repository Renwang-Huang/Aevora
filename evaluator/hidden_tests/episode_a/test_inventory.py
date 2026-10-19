"""Trusted Episode A invariants; all candidate calls cross the sandbox RPC.

The generic worker executes each batch in one process using multiple threads.
The checkpoint releases a real stale-read window when the candidate reaches
one; valid repairs need not retain that checkpoint or use a particular lock.
"""

import pytest

from evaluator.rpc import RemoteBusinessError


TEST_SUITE_VERSION = "1.0.0"
CHECKPOINT = {"label": "inventory_read", "timeout_seconds": 2.0}


def operations(count, quantity=1, prefix="purchase"):
    return [
        {"method": "create_order", "params": {
            "order_id": f"{prefix}-{index}", "sku": "SKU-1", "quantity": quantity,
        }}
        for index in range(count)
    ]


def execute(client, requests, workers, *, label="batch", controlled=True, restart=False):
    # Capture the full response and the trusted database BEFORE assertions.
    result = client.batch(
        requests, max_workers=workers, checkpoint=CHECKPOINT if controlled else None,
    )
    client.save_batch(result, label)
    oracle = client.database_oracle(label, restart=restart)
    return result, oracle


def assert_concurrent(batch, count):
    results = batch["results"]
    execution = batch["execution"]
    assert len(results) == count
    assert {item["index"] for item in results} == set(range(count))
    assert len({item["pid"] for item in results}) == 1
    assert {item["pid"] for item in results} == {execution["pid"]}
    assert len({item["thread_id"] for item in results}) >= 2
    assert len(execution["thread_ids"]) >= 2
    assert execution["max_active"] >= 2


def assert_purchase_outcomes(batch, oracle, requests, stock, quantity=1, *, concurrent=True):
    count = len(requests)
    if concurrent:
        assert_concurrent(batch, count)
    successes = [item for item in batch["results"] if item["ok"] is True]
    failures = [item for item in batch["results"] if item["ok"] is False]
    expected_success = min(count, stock // quantity)
    assert len(successes) == expected_success, batch
    assert len(failures) == count - expected_success
    assert all(item["error"]["type"] == "InsufficientInventory" for item in failures), failures
    assert all(item["result"]["status"] == "reserved" for item in successes)
    assert all(item["result"]["reservation_state"] == "active" for item in successes)
    succeeded_ids = {requests[item["index"]]["params"]["order_id"] for item in successes}
    assert len(succeeded_ids) == expected_success
    assert {item["result"]["order_id"] for item in successes} == succeeded_ids
    assert oracle["consistent"] is True, oracle["violations"]
    assert {order["order_id"] for order in oracle["orders"]} == succeeded_ids
    assert len(oracle["ledger"]) == expected_success
    assert {entry["order_id"] for entry in oracle["ledger"]} == succeeded_ids
    assert all(entry["action"] == "reserve" and entry["quantity"] == quantity
               for entry in oracle["ledger"])
    inventory = oracle["inventory"]
    assert len(inventory) == 1
    assert inventory[0]["initial_stock"] == stock
    assert inventory[0]["available"] == stock - expected_success * quantity
    assert inventory[0]["reserved"] == expected_success * quantity
    assert inventory[0]["committed"] == 0


def test_single_thread_purchase_and_exhaustion(client):
    client.initialize_fixture({"SKU-1": 7})
    accepted = [client.call("create_order", order_id=f"single-{index}", sku="SKU-1", quantity=1)
                for index in range(7)]
    with pytest.raises(RemoteBusinessError, match="InsufficientInventory"):
        client.call("create_order", order_id="single-rejected", sku="SKU-1", quantity=1)
    oracle = client.database_oracle()
    assert len(accepted) == 7
    assert oracle["consistent"] is True, oracle["violations"]
    assert oracle["inventory"][0]["available"] == 0
    assert oracle["inventory"][0]["reserved"] == 7
    assert len(oracle["orders"]) == len(oracle["ledger"]) == 7


def test_concurrent_200_requests_with_50_stock(client):
    requests = operations(200)
    batch, oracle = execute(client, requests, 200)
    assert_purchase_outcomes(batch, oracle, requests, 50)


def test_high_contention_one_remaining_item(client):
    client.initialize_fixture({"SKU-1": 1})
    requests = operations(40)
    batch, oracle = execute(client, requests, 20)
    assert_purchase_outcomes(batch, oracle, requests, 1)


@pytest.mark.parametrize("stock,count,workers,quantity", [
    (7, 40, 20, 1), (23, 100, 32, 1), (17, 40, 20, 3), (0, 40, 20, 1),
], ids=["stock7", "stock23", "quantity3", "stock0"])
def test_parameterized_conservation(client, stock, count, workers, quantity):
    client.initialize_fixture({"SKU-1": stock})
    requests = operations(count, quantity)
    batch, oracle = execute(client, requests, workers)
    assert_purchase_outcomes(batch, oracle, requests, stock, quantity)


def test_concurrent_invalid_requests_are_business_errors(client):
    requests = operations(10)
    invalid = [0, -1, True, 1.5, "1"]
    requests.extend({"method": "create_order", "params": {
        "order_id": f"invalid-{index}", "sku": "SKU-1", "quantity": value,
    }} for index, value in enumerate(invalid))
    batch, oracle = execute(client, requests, 15)
    assert_concurrent(batch, len(requests))
    successes = [item for item in batch["results"] if item["ok"]]
    failures = [item for item in batch["results"] if not item["ok"]]
    assert len(successes) == 10
    assert len(failures) == len(invalid)
    assert all(item["index"] >= 10 and item["error"]["type"] == "InvalidInput"
               for item in failures)
    assert oracle["consistent"] is True, oracle["violations"]
    assert oracle["inventory"][0]["available"] == 40
    assert oracle["inventory"][0]["reserved"] == 10
    assert {row["order_id"] for row in oracle["orders"]} == {
        f"purchase-{index}" for index in range(10)
    }


def test_cancel_and_repeat_cancel_preserve_ledger(client):
    client.call("create_order", order_id="cancel-regression", sku="SKU-1", quantity=3)
    for _ in range(4):
        assert client.call("cancel_order", order_id="cancel-regression")["status"] == "cancelled"
    client.call("release_inventory", order_id="cancel-regression")
    oracle = client.database_oracle()
    assert oracle["consistent"] is True, oracle["violations"]
    assert oracle["inventory"][0]["available"] == 50
    assert oracle["inventory"][0]["reserved"] == 0
    assert [row["action"] for row in oracle["ledger"]] == ["reserve", "release"]


def test_database_reset_and_repeat_concurrent_execution(client):
    for round_number in range(2):
        client.initialize_fixture({"SKU-1": 5})
        requests = operations(20, prefix=f"round-{round_number}")
        batch, oracle = execute(client, requests, 10, label=f"round-{round_number}", restart=True)
        assert_purchase_outcomes(batch, oracle, requests, 5)


def test_uncoordinated_concurrent_batch(client):
    client.initialize_fixture({"SKU-1": 11})
    requests = operations(40)
    batch, oracle = execute(client, requests, 20, controlled=False)
    assert_purchase_outcomes(batch, oracle, requests, 11)


def test_independent_skus_have_separate_reservation_accounts(client):
    stock = {"SKU-1": 6, "SKU-2": 9}
    client.initialize_fixture(stock)
    requests = operations(30, prefix="first-sku") + operations(30, prefix="second-sku")
    for item in requests[30:]:
        item["params"]["sku"] = "SKU-2"
    batch, oracle = execute(client, requests, 20)
    assert_concurrent(batch, len(requests))
    assert oracle["consistent"] is True, oracle["violations"]
    successes = [item for item in batch["results"] if item["ok"]]
    failures = [item for item in batch["results"] if not item["ok"]]
    assert all(item["error"]["type"] == "InsufficientInventory" for item in failures)
    assert len(successes) == sum(stock.values())
    for sku, quantity in stock.items():
        inventory = next(row for row in oracle["inventory"] if row["sku"] == sku)
        accepted_ids = {requests[item["index"]]["params"]["order_id"] for item in successes
                        if requests[item["index"]]["params"]["sku"] == sku}
        assert len(accepted_ids) == quantity
        assert inventory["available"] == 0
        assert inventory["reserved"] == quantity
        assert {row["order_id"] for row in oracle["orders"] if row["sku"] == sku} == accepted_ids
        assert {row["order_id"] for row in oracle["ledger"] if row["sku"] == sku} == accepted_ids


def test_creation_reservation_idempotence_regression(client):
    client.call("create_order", order_id="reserve-regression", sku="SKU-1", quantity=3, reserve=False)
    client.call("reserve_inventory", order_id="reserve-regression")
    client.call("reserve_inventory", order_id="reserve-regression")
    client.call("create_order", order_id="reserve-regression", sku="SKU-1", quantity=3)
    oracle = client.database_oracle()
    assert oracle["consistent"] is True, oracle["violations"]
    assert oracle["inventory"][0]["available"] == 47
    assert oracle["inventory"][0]["reserved"] == 3
    assert len(oracle["orders"]) == len(oracle["ledger"]) == 1


def test_insufficient_inventory_rolls_back_order_and_ledger(client):
    with pytest.raises(RemoteBusinessError, match="InsufficientInventory"):
        client.call("create_order", order_id="too-large", sku="SKU-1", quantity=51)
    oracle = client.database_oracle()
    assert oracle["consistent"] is True, oracle["violations"]
    assert oracle["inventory"][0]["available"] == 50
    assert oracle["orders"] == []
    assert oracle["ledger"] == []
