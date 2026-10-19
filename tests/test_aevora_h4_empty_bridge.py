"""Actual new graph + official MCP broker; no model or mocked repository."""
import json,socket,uuid
import pytest
from aevora.graph_repository import GraphRepository
from aevora.candidate import CandidateLifecycle
from integrations.aevora import AevoraRuntimeBridge
from scripts.aevora_h2_security import RPCClient

PUBLIC={'runtime':{'topology':'single_process_threads','database':'sqlite'}}

def test_native_bridge_accepts_real_initialized_empty_graph(monkeypatch,tmp_path):
    monkeypatch.setenv('AEVORA_FALKORDB_GRAPH','aevora_h4_empty_bridge_'+uuid.uuid4().hex)
    repo=GraphRepository.from_environment();CandidateLifecycle(repo).initialize()
    try:
        before=repo.state_fingerprint()
        with AevoraRuntimeBridge('empty-bridge',PUBLIC,tmp_path) as bridge:
            assert bridge.metadata['initial_corpus_state']=='EMPTY'
            assert bridge.metadata['initial_experience_count']==0
            assert bridge.metadata['initial_graph_state']==before
            c=RPCClient(bridge.broker,bridge.run_token,tmp_path/'actual-client.jsonl');c.initialize()
            response=c.tool('resolve_experience',{'task_context':{}});c.close()
            actual=response['result']['structuredContent']
            assert actual['status']=='AVAILABLE' and actual['candidates']==[]
            assert actual['run_id']=='empty-bridge'
        assert bridge.metadata['source_integrity']=='VERIFIED'
        assert bridge.run_token is None and not bridge.socket_path.exists()
        assert repo.experience_ids()==[]
        assert repo.query('MATCH(n:VerifiedOutcome) RETURN count(n)')==[[0]]
        assert repo.query('MATCH(n:Query) RETURN count(n)')==[[1]]
    finally:repo._graph.delete();repo.close()

def test_empty_bridge_does_not_hide_real_database_connection_failure(monkeypatch,tmp_path):
    from aevora.models import GraphUnavailable
    with socket.socket() as owned:
        owned.bind(('127.0.0.1',0));monkeypatch.setenv('AEVORA_FALKORDB_PORT',str(owned.getsockname()[1]))
        with pytest.raises(GraphUnavailable):AevoraRuntimeBridge('disconnected',PUBLIC,tmp_path)
    assert not list(tmp_path.iterdir())
