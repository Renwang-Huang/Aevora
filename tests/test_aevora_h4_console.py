"""Current built public Console: real package bytes and HTTP policy, no synthetic API."""
from hashlib import sha256
import json
from pathlib import Path
from starlette.testclient import TestClient
from aevora_observatory.server import create_app

ROOT=Path(__file__).resolve().parents[1]

def test_static_build_manifest_matches_all_delivered_bytes():
    root=ROOT/'console/src/aevora_observatory/static';receipt=json.loads((root/'BUILD_MANIFEST.json').read_text())
    for name,row in receipt['files'].items():
        path=root/name;expected=row['sha256'] if isinstance(row,dict) else row
        assert sha256(path.read_bytes()).hexdigest()==expected

def test_actual_index_preloads_cytoscape_external_style_without_unsafe_inline():
    pin=sha256((ROOT/'h4/hero_scenario_contract.json').read_bytes()).hexdigest()
    with TestClient(create_app(replay_root=ROOT/'h4',replay_sha256=pin),base_url='http://127.0.0.1') as c:
        res=c.get('/');assert res.status_code==200 and '__________cytoscape_stylesheet' in res.text
        assert "style-src 'self'" in res.headers['content-security-policy'] and 'unsafe-inline' not in res.headers['content-security-policy']
        assert c.get('/assets/app.css').status_code==200
        assert c.get('/assets/app.js').status_code==200

def test_public_graph_actions_and_stage_filter_are_present_in_actual_source():
    text=(ROOT/'console/web/app.js').read_text()
    assert 'selectedDecisions()' in text and 'd.context_name===state.stage' in text
    assert "cy.on('tap','node,edge'" in text and 'ResizeObserver' in text
    assert 'innerHTML' not in text

def test_frontend_dependency_versions_are_locked():
    package=json.loads((ROOT/'console/package.json').read_text());lock=json.loads((ROOT/'console/package-lock.json').read_text())
    for kind in ['dependencies','devDependencies']:
        for name,version in package[kind].items():assert lock['packages']['node_modules/'+name]['version']==version
