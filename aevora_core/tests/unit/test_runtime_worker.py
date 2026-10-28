"""Private Worker framing and Host authority contract; no database or model."""
import io
import struct

import pytest

from aevora.runtime_worker import read_packet, write_packet, strict_json, service_from_bootstrap
from aevora.backend_guard import backend_id


def test_worker_framing_rejects_ambiguous_or_unbounded_input():
    stream = io.BytesIO()
    write_packet(stream, {'value': 9007199254740993})
    stream.seek(0)
    assert read_packet(stream) == {'value': 9007199254740993}
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e9999}', b'{"x":"\\ud800"}', b'[]'):
        with pytest.raises(ValueError):
            strict_json(raw)
    with pytest.raises(ValueError):
        read_packet(io.BytesIO(struct.pack('>I', 262145)))


def test_worker_bootstrap_pins_trusted_facts(monkeypatch):
    monkeypatch.setenv('AEVORA_FALKORDB_HOST', '127.0.0.1')
    monkeypatch.setenv('AEVORA_FALKORDB_PORT', '17790')
    monkeypatch.setenv('AEVORA_FALKORDB_GRAPH', 'test')
    identity = backend_id('127.0.0.1', 17790, 'test')
    boot = dict(schema_version='aevora.worker-bootstrap/1', backend_id=identity,
        workspace_id=identity, run_id='trusted-run', facts={'worker_count': None},
        facts_version='public-context/1', facts_source='protected_host_profile', enable_proposals=False)
    service = service_from_bootstrap(boot, object())
    assert service.public_context == {'worker_count': None}
    assert service.run_id == 'trusted-run'
    with pytest.raises(ValueError):
        service_from_bootstrap({**boot, 'workspace_id': 'client-claim'}, object())
