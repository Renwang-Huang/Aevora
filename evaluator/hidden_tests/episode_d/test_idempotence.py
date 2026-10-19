"""Concurrent identity semantics without prescribing a synchronization strategy."""

import pytest

from .test_incident import assert_topology, assert_truth


@pytest.mark.parametrize("workers", [2, 4], ids=["workers2", "workers4"])
def test_concurrent_reserve_cancel_and_release_once(client, workers):
    pool = client.initialize({"SKU-1": 10}, workers)
    created = pool.call(0, "create_order", order_id="shared-reservation",
                        sku="SKU-1", quantity=3, reserve=False)
    assert (created["status"], created["reservation_state"]) == ("created", "none")
    reserves = [{"method": "reserve_inventory", "params": {"order_id": "shared-reservation"}}
                for _ in range(workers * 3)]
    reserved = client.batch(reserves, label="concurrent-reserve")
    assert_topology(reserved, workers)
    assert all(row["ok"] for row in reserved["results"]), reserved
    before_cancel = client.oracle(label="reserved-before-restart", requests=reserves,
                                  results=reserved["results"], restart=True)
    assert_truth(before_cancel)
    assert len(before_cancel["orders"]) == len(before_cancel["ledger"]) == 1
    assert before_cancel["orders"][0]["order_id"] == "shared-reservation"
    assert (before_cancel["orders"][0]["status"],
            before_cancel["orders"][0]["reservation_state"]) == ("reserved", "active")
    assert before_cancel["ledger"][0]["action"] == "reserve"
    assert before_cancel["inventory"][0]["available"] == 7
    assert before_cancel["inventory"][0]["reserved"] == 3

    # Existing API: release_inventory requires a cancelled order. Make that
    # precondition true via a real concurrent cancellation phase, preserving
    # strict successful-result assertions for every subsequent legal request.
    cancel_requests = [{"method": "cancel_order", "params": {"order_id": "shared-reservation"}}
                       for _ in range(workers * 3)]
    first_cancel = client.batch(cancel_requests, label="concurrent-first-cancel")
    assert_topology(first_cancel, workers)
    assert all(row["ok"] for row in first_cancel["results"]), first_cancel
    released = client.oracle(label="released-before-restart", requests=cancel_requests,
                             results=first_cancel["results"], restart=True)
    assert_truth(released)
    assert sorted(row["action"] for row in released["ledger"]) == ["release", "reserve"]
    assert released["inventory"][0]["available"] == 10
    assert released["inventory"][0]["reserved"] == 0

    cancellations = [{"method": "cancel_order" if index % 2 == 0 else "release_inventory",
                      "params": {"order_id": "shared-reservation"}}
                     for index in range(workers * 4)]
    cancelled = client.batch(cancellations, label="concurrent-cancel-release")
    assert_topology(cancelled, workers)
    assert all(row["ok"] for row in cancelled["results"]), cancelled
    after_cancel = client.oracle(label="cancelled", requests=cancellations,
                                 results=cancelled["results"])
    assert_truth(after_cancel)
    assert len(after_cancel["orders"]) == 1
    assert (after_cancel["orders"][0]["status"],
            after_cancel["orders"][0]["reservation_state"]) == ("cancelled", "released")
    assert sorted(row["action"] for row in after_cancel["ledger"]) == ["release", "reserve"]
    assert after_cancel["inventory"][0]["available"] == 10
    assert after_cancel["inventory"][0]["reserved"] == 0


@pytest.mark.parametrize("workers", [2, 4], ids=["workers2", "workers4"])
def test_concurrent_conflicting_payload_has_one_durable_winner(client, workers):
    stock = {"SKU-1": 11, "SKU-2": 13}
    client.initialize(stock, workers)
    payloads = [{"order_id": "contested-order", "sku": "SKU-1", "quantity": 2},
                {"order_id": "contested-order", "sku": "SKU-2", "quantity": 3}]
    traffic = [{"method": "create_order", "params": dict(payloads[index % 2])}
               for index in range(workers * 4)]
    batch = client.batch(traffic, label="concurrent-conflicting-payload")
    assert_topology(batch, workers)
    oracle = client.oracle(label="conflicting-payload", requests=traffic,
                           results=batch["results"])
    assert_truth(oracle)
    assert len(oracle["orders"]) == len(oracle["ledger"]) == 1
    winner = oracle["orders"][0]
    assert winner["order_id"] == "contested-order"
    assert (winner["status"], winner["reservation_state"]) == ("reserved", "active")
    assert {key: winner[key] for key in ("order_id", "sku", "quantity")} in payloads
    for result in batch["results"]:
        payload = traffic[result["index"]]["params"]
        matches_winner = all(payload[key] == winner[key] for key in ("order_id", "sku", "quantity"))
        if matches_winner:
            assert result["ok"], result
            assert all(result["result"][key] == winner[key]
                       for key in ("order_id", "sku", "quantity"))
        else:
            assert not result["ok"], result
            assert result["error"]["type"] == "OrderConflict", result
    assert oracle["ledger"][0]["action"] == "reserve"
    assert oracle["ledger"][0]["sku"] == winner["sku"]
    assert oracle["ledger"][0]["quantity"] == winner["quantity"]
    for row in oracle["inventory"]:
        reserved_quantity = winner["quantity"] if row["sku"] == winner["sku"] else 0
        assert row["available"] == stock[row["sku"]] - reserved_quantity
        assert row["reserved"] == reserved_quantity
