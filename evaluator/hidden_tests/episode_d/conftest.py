"""Trusted multi-process fixture; candidate imports occur only in sandbox."""
import json
import os
from pathlib import Path
import pytest

from evaluator.supervisor import WorkerSupervisor
from evaluator.episode_d_oracle import inspect_episode_d_database, recover_episode_d_database


class EpisodeDClient:
    def __init__(self, workspace, data_dir, artifacts, name):
        self.workspace, self.data_dir, self.artifacts, self.name = workspace, data_dir, artifacts, name
        self.pool = None
        self.stock = {}

    def save(self, kind, label, data):
        path = self.artifacts / f"{kind}-{self.name}-{label}.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    def initialize(self, stock, workers=2, *, wal=False):
        self.close()
        self.stock = dict(stock)
        self.pool = WorkerSupervisor(self.workspace, self.data_dir, self.artifacts,
                                     worker_count=workers).start()
        self.pool.initialize(self.stock, reset=True)
        if wal:
            # Host chooses the deployment mode before business traffic. No
            # candidate module is loaded into this trusted process.
            self.pool.stop_all()
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(self.data_dir / "business.sqlite")) as connection:
                assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            self.pool.start()
        return self.pool

    def batch(self, requests, label="batch", *, controlled=True):
        batch = self.pool.batch(requests, checkpoint={"label": "inventory_read", "timeout_seconds": 0.3}
                                if controlled else None)
        self.save("concurrency", label, batch)
        self.save("topology", label, self.pool.evidence())
        return batch

    def oracle(self, label="final", *, requests=None, results=None, required_workers=None,
               recover=False, restart=False):
        self.pool.stop_all()
        self.save("topology", label, self.pool.evidence())
        recovery = None
        if recover:
            recovery = recover_episode_d_database(self.data_dir / "business.sqlite",
                                                  data_dir=self.data_dir, workers_stopped=True)
            self.save("recovery", label + "-sqlite", recovery)
        oracle = inspect_episode_d_database(self.data_dir / "business.sqlite", expected_stock=self.stock,
                    data_dir=self.data_dir, requests=requests, results=results,
                    required_worker_ids=required_workers)
        if recovery is not None:
            oracle["sqlite_recovery"] = recovery
        self.save("oracle", label, oracle)
        if restart:
            self.pool.start()
        return oracle

    def close(self):
        if self.pool is not None:
            self.pool.close()
            self.save("topology", "cleanup", self.pool.evidence())
            self.pool = None


@pytest.fixture
def client(tmp_path, request):
    assert os.environ.get("ORDERFLOW_EXECUTION_STRATEGY") == "shared-db-workers"
    client = EpisodeDClient(Path(os.environ["ORDERFLOW_EVALUATION_WORKSPACE"]),
                          tmp_path / "database", Path(os.environ["ORDERFLOW_EVALUATION_ARTIFACTS"]),
                          request.node.name)
    try:
        yield client
    finally:
        client.close()
