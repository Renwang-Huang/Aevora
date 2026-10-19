"""Trusted fixtures run on the host, outside every candidate mount."""

import os
from pathlib import Path
import sys

import pytest

# -I and importlib mode omit the working directory. Add only this trusted
# package root, never the supplied candidate workspace.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluator.rpc import BusinessRPC


@pytest.fixture
def client(tmp_path, request):
    artifacts = Path(os.environ["ORDERFLOW_EVALUATION_ARTIFACTS"])
    rpc = BusinessRPC(
        Path(os.environ["ORDERFLOW_EVALUATION_WORKSPACE"]),
        tmp_path / "database",
        artifacts / f"worker-{request.node.name}.stderr.log",
    )
    try:
        rpc.start()
        rpc.call("initialize", stock={"SKU-1": 10, "SKU-2": 4}, reset=True)
        yield rpc
    finally:
        rpc.close()
