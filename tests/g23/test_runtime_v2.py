"""Real owned FalkorDB and official SDK; no model claims in these controls."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from copy import deepcopy
import json,os
import pytest
from aevora.contracts import *
from aevora_maintainer.native_source import structured
from tools.validation.g22_fixture import ready,proposal
from integrations.aevora import AevoraRuntimeBridge,public_runtime_context
from integrations.aevora_v2 import prepare_runtime_configuration,read_bootstrap
from aevora_core.tests.test_mcp_real_graph import connect,tool,rpc

def setup(host,tmp_path,monkeypatch):
    root=Path(os.environ['AEVORA_G22_ARTIFACT_ROOT'])/'g23'/tmp_path.name
    root.mkdir(parents=True);private=root/'bootstrap.json'
    c,review,prep=ready(host);receipt=host.publish(prep)
    report=json.loads((Path(host.case['root'])/'evaluation_report.json').read_text())
    body=dict(binding=host.repo.binding.__dict__,registry={'pin_root':str(host.pins.root)},facts=review['facts'],grant=dict(tenant=host.repo.tenant,session_id='cap-test-session',generation='g23-test',valid_until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),authz_epoch=host.repo.state()['authz_epoch'],profile=PROFILE))
    private.write_text(canonical_json(body));private.chmod(0o600)
    monkeypatch.setenv('AEVORA_FALKORDB_GRAPH',host.repo.binding.graph_name)
    return root,private,body,report['scenario_metadata']

def test_explicit_native_runtime_v2_bridge_uses_four_real_public_tools(host,tmp_path,monkeypatch):
    root,private,body,manifest=setup(host,tmp_path,monkeypatch)
    archive=root/'archive';archive.mkdir()
    b=AevoraRuntimeBridge('g23-bridge-test',manifest,archive,enable_proposals=True,protocol_profile=PROFILE,v2_bootstrap_path=private)
    with b:
        c,r=connect(b.broker,b.run_token)
        try:
            tools=rpc(c,r,2,'tools/list')['tools'];assert {t['name'] for t in tools}=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}
            q=tool(c,r,3,'resolve_experience',{'task_context':{}})['structuredContent'];assert q['candidate_count']==1 and q['recommendations'][0]['core_verdict']=='APPLY'
            p=proposal('native-bridge-unit');p['source_references']=[dict(kind='Query',id=q['query_id'])]
            result=tool(c,r,4,'propose_experience',{'proposal':p})
            assert result['structuredContent']['body_sha256']==digest(p)
            assert result['structuredContent']['read_scope']['run_id']=='g23-bridge-test'
        finally:r.close();c.close()
    assert b.metadata['protocol_profile']==PROFILE and b.metadata['broker']['token_revoked']
    assert not (archive/'HOST_V2_CONFIG.json').exists()

@pytest.mark.parametrize('attack',['world_readable','link','wrong_graph','wrong_tenant','wrong_facts','expired','extra','supplied_run'])
def test_runtime_bootstrap_does_not_grant_ambient_authority(host,tmp_path,monkeypatch,attack):
    root,p,body,manifest=setup(host,tmp_path,monkeypatch)
    if attack=='wrong_graph':body['binding']['graph_name']='unrelated_graph'
    if attack=='wrong_tenant':body['grant']['tenant']='another-tenant'
    if attack=='wrong_facts':
        manifest=deepcopy(manifest);manifest['runtime']['topology']='multi_process_shared_sqlite'
    if attack=='expired':body['grant']['valid_until']='2020-01-01T00:00:00Z'
    if attack=='extra':body['root_authority']='participant'
    if attack=='supplied_run':body['grant']['run_id']='other-run'
    p.write_text(canonical_json(body))
    if attack=='world_readable':p.chmod(0o644)
    if attack=='link':
        q=root/'linked.json';q.symlink_to(p);p=q
    out=root/'private-config';out.mkdir()
    with pytest.raises((V2Error,OSError)):
        prepare_runtime_configuration(p,'actual-run',public_runtime_context(manifest),out)

def test_same_body_different_native_candidate_cannot_rebind_host_source(host):
    p=proposal();c=host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'],origin='AGENT_PROPOSED',native_candidate_id='native:first')
    assert host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'],origin='AGENT_PROPOSED',native_candidate_id='native:first')==c
    with pytest.raises(V2Error,match='IMMUTABLE_CONFLICT'):
        host.propose(p,run_id=host.case['run_id'],tree_sha=host.case['tree_sha'],origin='AGENT_PROPOSED',native_candidate_id='native:other-actor')

def test_necessary_and_exclusion_on_same_fact_have_distinct_predicates(host):
    from tools.validation.g22_fixture import admitted
    from aevora.experience_resolver import resolve_v2
    from aevora.models import utc_now
    p=proposal('necessary-and-exclusion')
    p['inapplicable_conditions']={'task.shared_state_kind':['redis']}
    c,s,o,r=admitted(host,p=p)
    head=host.transition(c['id'],'PUBLISHING',expected_head=digest(host.head(c['id'])),reason='Distinct necessary/exclusion semantics')
    prepared=host.prepare(c['id'],r['id'],request_key='both-predicates',expected_head=digest(head),expected_epoch=host.repo.state()['epoch'])
    receipt=host.publish(prepared)
    state,rows=resolve_v2(host.repo,r['facts'],'query:both-predicates',utc_now())
    assert rows[0][0]['core_verdict']=='APPLY'
    premises=[n for n in rows[0][1]['nodes'].values() if n['kind']=='Premise']
    assert {(n['mode'],n['fact_key']) for n in premises}=={('necessary','task.shared_state_kind'),('exclusion','task.shared_state_kind')}

def test_even_pinned_unsupported_before_fact_needs_a_registered_extractor(host,tmp_path,monkeypatch):
    root,p,body,manifest=setup(host,tmp_path,monkeypatch)
    f=deepcopy(body['facts']['task.shared_state_kind'])
    f.update(key='artifact_before.authority_validation',phase='artifact_before',value='caller_claimed_valid')
    host.pins.put('fact_sources',digest(f),f['authority_ref'])
    body['facts'][f['key']]=f;p.write_text(canonical_json(body))
    out=root/'private-config';out.mkdir()
    with pytest.raises(V2Error,match='UNSUPPORTED_FACT_EXTRACTOR'):
        prepare_runtime_configuration(p,'actual-run',public_runtime_context(manifest),out)
