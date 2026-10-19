"""Trusted real OS-worker/Clock fixture, without candidate imports."""
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing

import pytest

from evaluator.dv02_supervisor import DV02WorkerSupervisor
from evaluator.episode_d_oracle import recover_episode_d_database
from evaluator.episode_d_v02_oracle import (
    inspect_episode_d_v02_database, inspect_acknowledged_history,
    require_recovery_evidence, RecoveryEvidenceUnavailable,
)


class DV02Client:
    def __init__(self, workspace, data_dir, artifacts, name):
        self.workspace, self.data_dir, self.artifacts, self.name = workspace, data_dir, artifacts, name
        self.pool, self.stock, self.snapshots = None, {}, []
        self.artifacts.mkdir(parents=True, exist_ok=True)

    def save(self, kind, label, data):
        path = self.artifacts / f"{kind}-{self.name}-{label}.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return path

    def initialize(self, stock, workers=2, *, wal=False):
        self.close()
        self.stock, self.snapshots = dict(stock), []
        self.pool = DV02WorkerSupervisor(self.workspace, self.data_dir, self.artifacts,
                                         worker_count=workers, clock_tick=100).start()
        self.pool.initialize(self.stock, reset=True)
        if wal:
            self.pool.stop_all()
            with closing(sqlite3.connect(self.data_dir / "business.sqlite")) as connection:
                assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            self.pool.start()
        return self.pool

    def claim(self, worker=0, request_id="r", order_id="o", sku="SKU-1", quantity=1, ttl=10):
        return self.pool.call(worker, "claim_request", request_id=request_id, order_id=order_id,
                              sku=sku, quantity=quantity, ttl=ttl)

    def batch(self, operations, label):
        result = self.pool.batch(operations, checkpoint=None)
        self.save("concurrency", label, result)
        self.save("topology", label, self.pool.evidence())
        return result

    def oracle(self, label="final", *, stop=True, restart=False, recover=False, **expectations):
        # Intermediate snapshots follow ACKs with no outstanding ordinary RPC;
        # paused processes remain paused, preserving the actual generation.
        if stop:
            self.pool.stop_all()
        topology = self.pool.evidence()
        self.save("topology", label, topology)
        identity = topology["shared_database"]
        recovery = None
        if recover:
            if not stop:
                raise ValueError("SQLite recovery requires stopped workers")
            recovery = recover_episode_d_database(self.data_dir / "business.sqlite", data_dir=self.data_dir,
                workers_stopped=True, expected_identity=(identity["device"], identity["inode"]))
            self.save("recovery", label + "-sqlite", recovery)
            if recovery["error"] is not None:
                raise RecoveryEvidenceUnavailable("RECOVERY_EVIDENCE_UNVERIFIED: native SQLite recovery failed")
        audit = inspect_episode_d_v02_database(self.data_dir / "business.sqlite", expected_stock=self.stock,
                    data_dir=self.data_dir, expected_identity=(identity["device"], identity["inode"]), **expectations)
        if recovery:
            audit["sqlite_recovery"] = recovery
        snapshot = {"label": label, "clock_tick": self.pool.clock.tick,
                    "quiescence": "WORKERS_STOPPED" if stop else "NO_OUTSTANDING_ORDINARY_CALL; ACK_BOUNDARY",
                    "audit": audit}
        self.snapshots.append(snapshot)
        audit["acknowledged_history"] = inspect_acknowledged_history(self.snapshots)
        self.save("oracle", label, audit)
        if restart:
            self.pool.start()
        return audit

    def close(self):
        if self.pool is not None:
            self.pool.close()
            self.save("topology", "cleanup", self.pool.evidence())
            self.pool = None


@pytest.fixture
def client(tmp_path, request):
    if os.environ.get("ORDERFLOW_EXECUTION_STRATEGY") != "shared-db-workers":
        raise RuntimeError("D-V02 requires actual shared-db-workers execution")
    instance = DV02Client(Path(os.environ["ORDERFLOW_EVALUATION_WORKSPACE"]), tmp_path / "database",
                          Path(os.environ["ORDERFLOW_EVALUATION_ARTIFACTS"]), request.node.name)
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture
def interrupted(client, request):
    """All mandatory recovery observations are checked during fixture setup.

    Unsupported instrumentation yields JUnit ERROR rather than a task failure.
    No candidate helper, SQL spelling or token format is prescribed.
    """
    method, label = request.param
    pool = client.initialize({"SKU-1": 10}, 2)
    params = {"request_id": "lost", "order_id": "lost-order", "sku": "SKU-1", "quantity": 3, "ttl": 10}
    handle = None
    if method == "complete_request":
        handle = client.claim(request_id="lost", order_id="lost-order", quantity=3)["handle"]
        params = {"handle": handle}
    before_call = client.oracle(method + "-" + label + "-claim-ack-before-call", stop=False)
    crash = pool.crash_call(0, method, label, **params)
    topology = pool.evidence()
    client.save("recovery", method + "-" + label, crash)
    client.save("topology", method + "-" + label, topology)
    try:
        proof = require_recovery_evidence(crash, topology, method=method, label=label)
    except RecoveryEvidenceUnavailable as error:
        client.save("recovery", method + "-" + label + "-unverified", {"status": "ERROR", "error": str(error),
            "method": method, "label": label, "raw_observation": crash})
        raise
    client.save("recovery", method + "-" + label + "-verified", proof)
    before = client.oracle(method + "-" + label + "-before-retry", recover=True, restart=True)
    return {"client": client, "method": method, "label": label, "params": params,
            "handle": handle, "crash": crash, "before": before, "before_call": before_call, "proof": proof}


@pytest.fixture
def crossed_deadline(client):
    from concurrent.futures import ThreadPoolExecutor
    pool=client.initialize({"SKU-1":5})
    handle=client.claim(ttl=10)["handle"]
    pool.arm_stop(0,"before_commit")
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(pool.call,0,"complete_request",handle=handle)
        boundary=pool.wait_stop(0,2)
        client.save("recovery","overlap-clock-before-commit",boundary)
        if boundary["availability"]!="AVAILABLE":
            pool.disarm(0)
            future.result(timeout=40)
            raise RecoveryEvidenceUnavailable("RECOVERY_EVIDENCE_UNVERIFIED: controlled COMMIT interval unavailable")
        try:
            pool.clock.advance(11)
        finally:
            pool.release(0)
        result=future.result(timeout=40)
    return {"result":result,"boundary":boundary,"audit":client.oracle("cross-deadline")}


@pytest.fixture
def stale_interrupted(client):
    pool=client.initialize({"SKU-1":5})
    old=client.claim(ttl=1)["handle"]
    pool.clock.advance(1)
    new=client.claim(1,ttl=30)
    before=client.oracle("stale-lost-ack-before",stop=False)
    crash=pool.crash_call(0,"complete_request","before_response",handle=old)
    crash["phase"]="stale-cleanup"
    topology=pool.evidence()
    client.save("recovery","stale-cleanup-before_response",crash)
    client.save("topology","stale-cleanup-before_response",topology)
    try:
        proof=require_recovery_evidence(crash,topology,method="complete_request",label="before_response",readonly_stale=True)
    except RecoveryEvidenceUnavailable as error:
        client.save("recovery","stale-cleanup-unverified",{"status":"ERROR","error":str(error),"raw_observation":crash})
        raise
    proof["phase"]="stale-cleanup"
    client.save("recovery","stale-cleanup-verified",proof)
    recovered=client.oracle("stale-lost-ack-recovery",recover=True,restart=True)
    return {"client":client,"old":old,"new":new,"before":before,"recovered":recovered,"proof":proof,"crash":crash}



@pytest.fixture
def capacity_environment(client, request):
    """Prepare real ample-stock writes and mandatory FD evidence before grading.

    Observation absence is ERROR during setup. The business response, capacity
    and raw database assertions remain in the test body and are not relaxed.
    """
    workers,stock,quantity,wal=request.param
    pool=client.initialize({"SKU-1":stock,"SKU-2":workers},workers,wal=wal)
    witness_handles=[]
    for worker in range(workers):
        granted=client.claim(worker,request_id=f"w{worker}",order_id=f"w-order-{worker}",sku="SKU-2")
        witness_handles.append(granted["handle"])
    witness=client.batch([{"method":"complete_request","params":{"handle":handle}} for handle in witness_handles],"write-witness")
    topology=pool.evidence()
    database=topology["shared_database"]
    missing=[]
    for worker in range(workers):
        if not any(row["worker_index"]==worker and row["method"]=="complete_request" and row["matching_fds"]
                   and row["database"]["device"]==database["device"] and row["database"]["inode"]==database["inode"]
                   for row in topology["database_fd_witnesses"]):
            missing.append(worker)
    if missing:
        client.save("topology","mandatory-write-witness-unverified",{"status":"ERROR","missing_workers":missing,
                    "raw_topology":topology,"reason":"RECOVERY_EVIDENCE_UNVERIFIED: required target DB FD observation unavailable"})
        raise RecoveryEvidenceUnavailable("RECOVERY_EVIDENCE_UNVERIFIED: required target DB FD write witnesses unavailable for workers "+str(missing))
    return {"client":client,"workers":workers,"stock":stock,"quantity":quantity,"wal":wal,"witness":witness}


@pytest.fixture
def existing_unreserved_interrupted(client):
    """Observe the real existing-order branch, with one subsequent writer.

    Public create and claim ACKs precede the independent raw before snapshot.
    An absent commit/FD/kill witness is infrastructure ERROR during setup.
    The observer selects a generic commit, never a specific candidate helper.
    """
    pool = client.initialize({"SKU-1": 10}, 2)
    pool.call(0, "create_order", order_id="existing-order", sku="SKU-1", quantity=3, reserve=False)
    handle = client.claim(request_id="existing", order_id="existing-order", quantity=3)["handle"]
    before_call = client.oracle("existing-unreserved-claim-ack-before-call", stop=False)
    crash = pool.crash_call(0, "complete_request", "transaction_committed", handle=handle)
    crash["phase"] = "existing-unreserved"
    topology = pool.evidence()
    client.save("recovery", "existing-unreserved-transaction_committed", crash)
    client.save("topology", "existing-unreserved-transaction_committed", topology)
    try:
        proof = require_recovery_evidence(crash, topology, method="complete_request", label="transaction_committed")
    except RecoveryEvidenceUnavailable as error:
        client.save("recovery", "existing-unreserved-unverified", {"status": "ERROR", "error": str(error),
                    "raw_observation": crash})
        raise
    proof["phase"] = "existing-unreserved"
    client.save("recovery", "existing-unreserved-verified", proof)
    recovered = client.oracle("existing-unreserved-after-crash", recover=True, restart=True)
    return {"client": client, "handle": handle, "before_call": before_call,
            "recovered": recovered, "crash": crash, "proof": proof}
