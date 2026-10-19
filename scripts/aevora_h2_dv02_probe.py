"""Actual bounded two-process transport/authority probe, independent of scoring."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.episodes.episode_d_v02 import build_episode_d_v02
from evaluator.dv02_supervisor import DV02WorkerSupervisor


def run(destination):
    destination.mkdir(parents=True, exist_ok=False)
    results = []
    for implementation in ("buggy", "reference", "flock", "local_lock", "blind_cleanup"):
        scope = destination / implementation
        workspace = build_episode_d_v02(scope / "workspace", implementation=implementation)
        source = {path.relative_to(workspace).as_posix(): sha256(path.read_bytes()).hexdigest()
                  for path in sorted((workspace / "app").glob("*.py"))}
        pool = DV02WorkerSupervisor(workspace, scope / "data", scope / "artifacts")
        observations = {}
        try:
            pool.start()
            pool.initialize({"SKU": 10})
            first = pool.call(0, "claim_request", request_id="takeover", order_id="order", sku="SKU", quantity=2, ttl=10)
            observations["first"] = first
            observations["pause"] = pool.pause(0)
            pool.clock.advance_to(110)
            second = pool.call(1, "claim_request", request_id="takeover", order_id="order", sku="SKU", quantity=2, ttl=10)
            observations["second"] = second
            observations["resume"] = pool.resume(0)
            observations["late_completion"] = pool.call(0, "complete_request", handle=first["handle"])
            with sqlite3.connect(pool.data_dir / "business.sqlite") as connection:
                observations["before_current_completion"] = {
                    "request": connection.execute("SELECT status,current_token,deadline FROM requests WHERE request_id='takeover'").fetchone(),
                    "orders": connection.execute("SELECT order_id,status FROM orders").fetchall(),
                    "ledger": connection.execute("SELECT action,quantity FROM inventory_ledger").fetchall()}
            observations["current_completion"] = pool.call(1, "complete_request", handle=second["handle"])
            third = pool.call(0, "claim_request", request_id="cancel", order_id="cancel-order", sku="SKU", quantity=1, ttl=10)
            observations["cancel"] = pool.call(1, "cancel_request", request_id="cancel")
            observations["late_after_cancel"] = pool.call(0, "complete_request", handle=third["handle"])
            with sqlite3.connect(pool.data_dir / "business.sqlite") as connection:
                observations["after_cancel"] = connection.execute("SELECT status FROM requests WHERE request_id='cancel'").fetchone()
        finally:
            topology = pool.close()
        generations = topology["identity_generations"]
        assert len({row["host_pid"] for row in generations}) == 2
        assert topology["cleanup"]["complete"] and topology["clock"]["cleanup"]["complete"]
        assert len(topology["database_fd_witnesses"]) >= 2
        assert {row["event"] for row in topology["clock"]["events"]} >= {"clock.now", "clock.advanced"}
        assert observations["first"]["handle"]["token"] != observations["second"]["handle"]["token"]
        expected_valid = implementation in ("reference", "flock", "blind_cleanup")
        before = observations["before_current_completion"]
        assert before["request"][0] == ("PENDING" if expected_valid else "COMPLETED")
        assert before["orders"] == ([] if expected_valid else [("order", "reserved")])
        assert observations["after_cancel"][0] == ("CANCELLED" if expected_valid else "COMPLETED")
        row = {"implementation": implementation, "source_sha256": source,
               "transport_probe": "PASS", "task_grade": "NOT_A_HIDDEN_EVALUATION",
               "observations": observations, "topology": topology}
        (scope / "PROBE.json").write_text(json.dumps(row, indent=2) + "\n")
        results.append({"implementation": implementation, "transport_probe": "PASS", "artifact": str(scope / "PROBE.json")})
    (destination / "SUMMARY.json").write_text(json.dumps({"status": "PASS", "results": results}, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    run(parser.parse_args().destination.absolute())
