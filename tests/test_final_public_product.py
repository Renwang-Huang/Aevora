"""New local product acceptance. Real owned Graph; no model API requests."""
from pathlib import Path
import json
import pytest
from starlette.testclient import TestClient
from aevora import demo
from aevora_observatory.server import create_app

ROOT=Path(__file__).resolve().parents[1]
PIN='c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776'

@pytest.fixture(scope='module')
def demo_state(tmp_path_factory):
    p=tmp_path_factory.mktemp('public-gen2-state')
    # The suite owns a new prefix, not an existing service graph.
    import os,uuid
    old=os.environ['AEVORA_FALKORDB_GRAPH'];os.environ['AEVORA_FALKORDB_GRAPH']='aevora_v2_public_test_'+uuid.uuid4().hex
    try:
        result=demo.seed(p);assert result['public_verifier']['verdict']=='PASS';yield p
    finally:os.environ['AEVORA_FALKORDB_GRAPH']=old

@pytest.mark.parametrize('context,stage,expected',[
    ('threads','before','APPLY'),('workers','before','ABSTAIN'),('unknown','before','VERIFY'),
    ('threads','after','ABSTAIN'),('workers','after','ABSTAIN'),('unknown','after','ABSTAIN'),
])
def test_actual_graph_v2_journey(demo_state,context,stage,expected):
    x=demo.observe(demo_state,context,stage)
    assert x['recommendation']['core_verdict']==expected
    assert x['graph']['edges'] and x['graph']['nodes']
    assert x['query_receipts'] and x['fallback'] is False
    assert x['mode']=='LIVE_SYNTHETIC_DEMO' and x['model_execution'] is False

@pytest.fixture
def viewer(demo_state):
    return TestClient(create_app(replay_root=ROOT/'h4',replay_sha256=PIN,demo_state=demo_state),base_url='http://127.0.0.1')

def test_http_live_projection_and_root(viewer):
    response=viewer.get('/api/journey?context=threads&stage=before');assert response.status_code==200
    assert response.json()['recommendation']['core_verdict']=='APPLY'
    assert response.headers['cache-control']=='no-store'
    assert "default-src 'self'" in response.headers['content-security-policy']
    assert viewer.get('/',follow_redirects=False).headers['location']=='/journey.html'

@pytest.mark.parametrize('method',['post','put','patch','delete'])
def test_browser_has_no_write_authority(viewer,method):
    response=getattr(viewer,method)('/api/journey');assert response.status_code==403

@pytest.mark.parametrize('query',['context=threads&context=workers','tenant=other','graph=private','context=../private','stage=unknown'])
def test_closed_http_selectors(viewer,query):
    assert viewer.get('/api/journey?'+query).status_code==400

def test_http_origin_boundary(viewer):
    assert viewer.get('/api/journey',headers={'origin':'https://other.invalid'}).status_code==403
    assert viewer.get('/api/journey',headers={'host':'other.invalid'}).status_code==403

def test_graph_unavailable_never_replays(viewer,monkeypatch):
    monkeypatch.setenv('AEVORA_FALKORDB_PORT','1')
    r=viewer.get('/api/journey');assert r.status_code==503
    assert r.json()=={'status':'UNAVAILABLE','error':'LIVE_GRAPH_READ_FAILED','fallback':False}

def test_demo_seed_cannot_overwrite(demo_state):
    with pytest.raises(ValueError,match='Fresh demo state required'):demo.seed(demo_state)

def test_historical_summary_keeps_actual_agent_choice():
    d=json.loads((ROOT/'console/web/gen2_history.json').read_text())
    assert d['core_recommendation']=='APPLY' and d['agent_choice']=='VERIFY'
    assert d['causal_benefit']=='UNKNOWN' and d['g24_formal']=='NOT_RUN'
    assert [r['passed'] for r in d['runs']]==[28,28]
    assert [r['native_children'] for r in d['runs']]==[3,3]


def test_public_launcher_preserves_maintainer_entry():
    old=(ROOT/'scripts/aevora_demo.py').read_text()
    new=(ROOT/'scripts/aevora_public_demo.py').read_text()
    assert 'verify-existing' in old and 'def main' in old
    assert 'aevora-gen2-demo' in new
    from tools.public_release import chosen
    selected={str(p.relative_to(ROOT)) for p in chosen()}
    assert 'scripts/aevora_public_demo.py' in selected
    assert 'scripts/aevora_demo.py' in selected


def test_public_ignore_protects_future_local_credentials():
    text=(ROOT/'.gitignore').read_text()
    assert '.env\n.env.*\n!.env.example' in text


def test_full_selection_includes_recovery_and_reproduction():
    from tools.public_release import chosen
    selected={str(p.relative_to(ROOT)) for p in chosen()}
    assert 'aevora_core/docs/H2_RECOVERY_VALIDATION.md' in selected
    assert 'aevora_core/docs/H1_REPRODUCTION.md' in selected
    assert (ROOT/'aevora_core/docs/H2_RECOVERY_VALIDATION.md').is_file()
    assert 'aevora_core/docs/GRAPH_V2_ARBITRATION.md' in selected
