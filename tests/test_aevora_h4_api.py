"""Actual ASGI code and real isolated FalkorDB; no repository/result mocks."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import socket
import uuid

import pytest
from starlette.testclient import TestClient
from aevora.graph_repository import GraphRepository
from aevora.experience_resolver import ExperienceResolver
from aevora_observatory.server import create_app
from aevora_observatory.projection import CONTEXTS,activity

ROOT=Path(__file__).resolve().parents[1];PIN=sha256((ROOT/'h4/hero_scenario_contract.json').read_bytes()).hexdigest()


def client(**kwargs):return TestClient(create_app(replay_root=ROOT/'h4',replay_sha256=PIN,**kwargs),base_url='http://127.0.0.1')


@pytest.fixture
def repo(monkeypatch):
    name='aevora_h4_api_test_'+uuid.uuid4().hex
    monkeypatch.setenv('AEVORA_FALKORDB_GRAPH',name)
    r=GraphRepository.from_environment()
    from tools.validation.legacy_fixture import seed_process_lock
    seed_process_lock(r)
    try:yield r
    finally:r._graph.delete();r.close()


def test_three_replay_acts_are_distinct_and_pinned():
    with client() as c:
        for case in ['case-a','case-b','case-c']:
            res=c.get('/api/overview',params={'case':case});assert res.status_code==200
            v=res.json();assert v['mode']=='REPLAY' and v['case']['case_id']==case and v['contract_sha256']==PIN
            assert v['health']['database']=='NOT_PROBED_REPLAY' and v['causal_benefit']=='UNKNOWN'


def test_actual_live_authority_and_reads_do_not_write(repo):
    before=repo.state_fingerprint()
    direct=ExperienceResolver(repo).resolve(CONTEXTS['workers'],persist_snapshots=False)
    expected={x['experience_id']:x['decision'] for x in direct['candidates']}
    with client() as c:
        v=c.get('/api/overview',params={'mode':'LIVE','case':'case-b'}).json()
        assert v['mode']=='LIVE' and v['health']['database']=='AVAILABLE' and v['archive'] is None
        assert v['decisions'][0]['decision']==expected[v['decisions'][0]['experience_id']]=='ABSTAIN'
        assert v['context_authority'].startswith('MAINTAINER_CONTROLLED_PUBLIC_CONTEXT')
        assert all(n['id'] for n in v['graph']['nodes'])
    assert repo.state_fingerprint()==before


@pytest.mark.parametrize('stage,edge_present',[('before',True),('after',False),('restored',True)])
def test_control_graph_stage_matches_actual_removed_edge(stage,edge_present):
    with client() as c:
        v=c.get('/api/overview',params={'case':'case-c','stage':stage}).json()
        target=v['evolution']['selected_edge']['id'];assert v['evolution_stage']==stage
        assert (target in {e['id'] for e in v['graph']['edges']})==edge_present


@pytest.mark.parametrize('path', ['/api/review','/api/cypher','/api/outcomes','/api/proof/graph'])
def test_actual_http_write_methods_forbidden(path):
    with client() as c:assert c.post(path,json={'publish':'never','statement':'DELETE n'}).status_code==403


@pytest.mark.parametrize('params',[
 {'mode':'pretend-live'}, {'case':'fake-case'}, {'context':'override-private'},
 {'stage':'fabricated'}, {'limit':'1000000'}, {'offset':'-1'}, {'path':'/etc/passwd'},
 {'cypher':'MATCH(n) DELETE n'}, {'experience':"x' DELETE n"},
])
def test_bounded_selectors_reject_malformed_input(params):
    with client() as c:assert c.get('/api/overview',params=params).status_code==400


def test_duplicate_query_parameters_rejected():
    with client() as c:assert c.get('/api/overview?mode=LIVE&mode=REPLAY').status_code==400


@pytest.mark.parametrize('headers',[{'origin':'https://unrelated.example'},{'host':'unrelated.example'},{'host':'testserver'},{'host':'['}])
def test_viewer_origin_and_host_boundary(headers):
    with client() as c:assert c.get('/api/overview',headers=headers).status_code==403


def test_public_response_has_no_raw_privileged_fields(repo):
    with client() as c:
        for mode in ['LIVE','REPLAY']:
            res=c.get('/api/overview',params={'mode':mode,'case':'case-b'});assert res.status_code==200
            assert all(v not in res.text for v in ['AEVORA_RUN_TOKEN','/home/private-user/.config/','private_verification','raw_mcp_payload','hidden_tests/test_'])
            assert res.headers['cache-control']=='no-store'


def test_disconnected_database_never_falls_back_to_replay(monkeypatch):
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0));monkeypatch.setenv('AEVORA_FALKORDB_PORT',str(reserved.getsockname()[1]))
        with client() as c:
            res=c.get('/api/overview',params={'mode':'LIVE'});assert res.status_code==503
            assert res.json()['mode']=='LIVE' and res.json()['fallback'] is False
            assert c.get('/api/overview',params={'mode':'REPLAY'}).status_code==200


def test_empty_real_graph_is_empty_no_history_import(repo,monkeypatch):
    name='aevora_h4_api_empty_'+uuid.uuid4().hex;monkeypatch.setenv('AEVORA_FALKORDB_GRAPH',name)
    empty=GraphRepository.from_environment();empty.initialize()
    try:
        with client() as c:
            v=c.get('/api/overview',params={'mode':'LIVE','case':'case-b'}).json()
            assert v['status']=='EMPTY' and v['experiences']==v['decisions']==[] and v['outcomes']['trusted']==[]
    finally:empty._graph.delete();empty.close()


def test_unavailable_natural_live_source_not_filled_from_replay(repo):
    with client() as c:
        v=c.get('/api/overview',params={'mode':'LIVE','case':'case-a'}).json()
        assert v['status']=='UNAVAILABLE' and v['lifecycle'] is None and v['mode']=='LIVE'


def test_actual_oversized_graph_fails_before_unbounded_reads(repo):
    for i in range(501):repo.put_node('Agent',{'id':'explicit-size-control-'+str(i),'runtime':'EXPLICIT_TEST_FIXTURE'})
    with client() as c:
        res=c.get('/api/overview',params={'mode':'LIVE'});assert res.status_code==413
        assert res.json()['error']=='GRAPH_READ_BUDGET_EXCEEDED' and res.json()['fallback'] is False


def test_independent_replay_tamper_detected_after_startup(tmp_path):
    replay=tmp_path/'replay';replay.mkdir();shutil.copytree(ROOT/'h4/replay',replay/'replay');shutil.copyfile(ROOT/'h4/hero_scenario_contract.json',replay/'hero_scenario_contract.json')
    with TestClient(create_app(replay_root=replay,replay_sha256=PIN),base_url='http://127.0.0.1') as c:
        with (replay/'replay/origin.json').open('ab') as f:f.write(b' ')
        assert c.get('/api/overview').status_code==422


def test_only_named_public_proofs_readable():
    with client() as c:
        assert c.get('/api/proof/origin').status_code==200
        assert c.get('/api/proof/private-manifest').status_code==403
        assert c.get('/api/proof/origin?path=/etc/passwd').status_code==400


def test_native_activity_public_header_is_exact_bytes(tmp_path):
    p=tmp_path/'g4/native/test/runs/actual-run';p.mkdir(parents=True)
    value={'run_id':'actual-run','runtime_result':'ERROR','failure_kind':'NO_PATCH','thread_id':'native-observed','session_id':'native-observed','raw_private_data':'must-not-project'}
    q=p/'runtime_metadata.json';q.write_text(json.dumps(value));v=activity(tmp_path)
    assert v[0]['source_sha256']==sha256(q.read_bytes()).hexdigest() and 'raw_private_data' not in v[0]


def test_vendor_is_exact_public_source_no_new_when_logic():
    d=ROOT/'console/src/aevora_observatory'
    assert (d/'_hero_verify.py').read_bytes()==(ROOT/'h4/verify_hero.py').read_bytes()
    assert (d/'_public_projection.py').read_bytes()==(ROOT/'h4/public_projection.py').read_bytes()


def test_actual_typed_header_exposes_snapshot_time_and_unknown_liveness(tmp_path):
    # File-protocol contract fixture, never claimed as native execution evidence.
    run=tmp_path/'g9/native/contract/runs/unit-fixture';run.mkdir(parents=True)
    (run/'runtime_status.json').write_text(json.dumps({'run_id':'unit-fixture','status':'RUNNING','observed_at':'2026-01-01T00:00:00Z','evidence_status':'PARTIAL_SNAPSHOT'}))
    rows=activity(tmp_path);assert rows[0]['header_observed_at']=='2026-01-01T00:00:00Z'
    assert rows[0]['process_liveness']=='UNAVAILABLE_NOT_PROBED' and rows[0]['evidence_status']=='PARTIAL_SNAPSHOT'


def test_actual_append_only_event_file_waits_for_complete_tail(tmp_path):
    run=tmp_path/'g9/native/contract/runs/unit-fixture';run.mkdir(parents=True)
    (run/'runtime_status.json').write_text(json.dumps({'run_id':'unit-fixture','status':'RUNNING'}))
    event=json.dumps({'category':'JSONRPC','timestamp':'2026-01-01T00:00:00Z','raw_json':json.dumps({'method':'tools/call','params':{'name':'resolve_experience'}})}).encode()
    log=run/'aevora_mcp_events.jsonl';log.write_bytes(event+b'\n'+event[:12])
    row=activity(tmp_path)[0];assert row['event_stream_status']=='PARTIAL_INCOMPLETE_TAIL' and row['incomplete_tail_bytes']==12 and len(row['tool_events'])==1
    with log.open('ab') as f:f.write(event[12:]+b'\n')
    row=activity(tmp_path)[0];assert row['event_stream_status']=='COMPLETE_OBSERVED_PREFIX' and len(row['tool_events'])==2
    log.write_bytes(event+b'\nmalformed complete event\n')
    with pytest.raises(ValueError):activity(tmp_path)


def test_owned_core_channel_uses_actual_file_headers_no_payload(tmp_path):
    from aevora_observatory.projection import channel_activity
    event={'source':'aevora.authenticated_mcp_broker','run_id':'contract-fixture','category':'JSONRPC','timestamp':'2026-01-01T00:00:00Z','raw_json':json.dumps({'method':'tools/call','params':{'name':'resolve_experience','arguments':{'private_context':'must-not-project'}}})}
    p=tmp_path/'events.jsonl';p.write_text(json.dumps(event)+'\n');row=channel_activity(p)[0]
    assert row['run_id']=='contract-fixture' and row['session_id'] is None and len(row['tool_events'])==1
    assert 'must-not-project' not in json.dumps(row) and row['status']=='MCP_REQUESTS_OBSERVED'
    event['run_id']='another-channel'
    with p.open('a') as f:f.write(json.dumps(event)+'\n')
    with pytest.raises(ValueError):channel_activity(p)


def test_owned_channel_input_is_not_browser_controlled(tmp_path):
    p=tmp_path/'ordinary.jsonl';p.write_text(json.dumps({'source':'private-invalid-source','run_id':'fake','category':'JSONRPC'})+'\n')
    from aevora_observatory.projection import channel_activity
    with pytest.raises(ValueError):channel_activity(p)
    with client() as c:assert c.get('/api/sessions?mcp_events=/etc/passwd').status_code==400
