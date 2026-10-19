"""Host-owned fixtures and evidence collection for concurrent business RPC."""

import json
import os
from pathlib import Path

import pytest

from evaluator.oracle import inspect_database
from evaluator.rpc import BusinessRPC


class EpisodeClient(BusinessRPC):
    def __init__(self, workspace, data_dir, artifacts, test_name):
        super().__init__(workspace, data_dir, artifacts / f"worker-{test_name}.stderr.log")
        self.artifacts = artifacts
        self.test_name = test_name
        self.expected_stock = {}

    def initialize_fixture(self, stock):
        # This fixture is chosen by the trusted host, not candidate metadata.
        self.expected_stock = dict(stock)
        self.call("initialize", stock=self.expected_stock, reset=True)

    def save_batch(self, batch, label="batch"):
        path = self.artifacts / f"concurrency-{self.test_name}-{label}.json"
        path.write_text(json.dumps(batch, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def database_oracle(self, label="final", *, restart=False):
        # Stop all candidate threads before reading the actual database file.
        self.close()
        result = inspect_database(
            self.data_dir / "business.sqlite", expected_stock=self.expected_stock,
            data_dir=self.data_dir,
        )
        path = self.artifacts / f"oracle-{self.test_name}-{label}.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if restart:
            self.start()
        return result


@pytest.fixture
def client(tmp_path, request):
    artifacts = Path(os.environ["ORDERFLOW_EVALUATION_ARTIFACTS"])
    rpc = EpisodeClient(
        Path(os.environ["ORDERFLOW_EVALUATION_WORKSPACE"]),
        tmp_path / "database", artifacts, request.node.name,
    )
    try:
        rpc.start()
        rpc.initialize_fixture({"SKU-1": 50})
        yield rpc
    finally:
        rpc.close()
