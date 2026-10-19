"""Real, separately named owned graphs; no mock repositories."""

import os, uuid
import pytest
from aevora.graph_repository import GraphRepository
from aevora.contracts import TenantBinding, TrustRegistry


@pytest.fixture
def v2():
    main = GraphRepository.from_environment()
    name = "aevora_v2_g21_test_" + uuid.uuid4().hex
    transport = GraphRepository(
        host="127.0.0.1",
        port=int(os.environ["AEVORA_FALKORDB_PORT"]),
        password=main._client.connection.connection_pool.connection_kwargs["password"],
        graph_name=name,
    )
    main.close()
    repo = transport.v2(TenantBinding("tenant-g21", name), TrustRegistry())
    repo.initialize()
    yield repo
    # Retain graphs in owned external DB for Full evidence/recovery, never delete an old graph.
    transport.close()
