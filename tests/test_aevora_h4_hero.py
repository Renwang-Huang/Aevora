"""Additive Hero contract checks against actual frozen public H3 projections."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest
from examples.observatory.verify_hero import verify
from examples.observatory.public_projection import project

SOURCE=Path(__file__).resolve().parents[1]/'examples/observatory'


@pytest.fixture
def replay(tmp_path):
    root=tmp_path/'hero';root.mkdir()
    shutil.copytree(SOURCE/'replay',root/'replay')
    shutil.copyfile(SOURCE/'hero_scenario_contract.json',root/'hero_scenario_contract.json')
    return root


def pin(root):return sha256((root/'hero_scenario_contract.json').read_bytes()).hexdigest()


def mutate(root,artifact,change):
    contract=json.loads((root/'hero_scenario_contract.json').read_text())
    if artifact=='contract':
        change(contract)
    else:
        path=root/contract['artifacts'][artifact]['artifact_path'];value=json.loads(path.read_text());change(value)
        path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')
        contract['artifacts'][artifact]['sha256']=sha256(path.read_bytes()).hexdigest()
    (root/'hero_scenario_contract.json').write_text(json.dumps(contract,sort_keys=True,allow_nan=False)+'\n')


def test_actual_public_hero_verifies(replay):
    result=verify(replay,pin(replay));assert result['acts']==3 and result['native_children']==3


@pytest.mark.parametrize('artifact,mutation',[
 ('contract',lambda c:c['acts'][0].update(run_id='forged-run')),
 ('contract',lambda c:c['acts'][0].update(source_commit='later-source-epoch')),
 ('contract',lambda c:c['acts'][1].update(rule_id='rule:wrong')),
 ('contract',lambda c:c['acts'][1].update(decision_id='invented-persisted-decision')),
 ('contract',lambda c:c['acts'][2].update(outcome_id='invented-agent-outcome')),
 ('contract',lambda c:c.update(mode='LIVE')),
 ('contract',lambda c:c.update(same_experience_across_acts=True)),
 ('contract',lambda c:c.update(agent_adoption='PROVEN')),
 ('contract',lambda c:c['artifacts']['graph'].update(visibility='MAINTAINER_ONLY')),
 ('origin',lambda x:x.update(outcome_id='orderflow:forged')),
 ('origin',lambda x:x['test_counts'].update(skipped=1)),
 ('origin',lambda x:x['children'][0].update(parent_thread_id='different-session')),
 ('origin',lambda x:x['children'][0].update(completed=False)),
 ('readback',lambda x:x.update(run_id='405c481e-ae7a-420d-8502-fb1d9ede02e6')),
 ('readback',lambda x:x.update(evaluation='PASS')),
 ('lifecycle',lambda x:x['events'][1].update(authority='UNTRUSTED_PROPOSAL')),
 ('lifecycle',lambda x:x['events'][2].update(previous_event_id='broken-chain')),
 ('graph',lambda x:x['edges'][0].update(target='invented-node')),
 ('graph',lambda x:x['nodes'].append(deepcopy(x['nodes'][0]))),
 ('graph',lambda x:x['nodes'][0]['public'].update(raw_mcp_payload='must-not-be-public')),
 ('graph',lambda x:x['edges'].__setitem__(slice(None),[e for e in x['edges'] if e['relation']!='PUBLISHED_FROM'])),
 ('evolution',lambda x:x['selected_edge'].update(target='wrong-outcome')),
 ('evolution',lambda x:x['historical_replay'].update(retrieval_snapshot_sha256='0'*64)),
 ('evolution',lambda x:x['after'].update(decision='APPLY')),
 ('evolution',lambda x:x.update(agent_outcome_id='made-up-outcome')),
 ('queries',lambda x:[q.update(cypher='RETURN 1') for q in x['queries']]),
 ('pilot',lambda x:x['raw_memory'].update(passed=0)),
 ('pilot',lambda x:x.update(authority='VERIFIED')),
 ('pilot',lambda x:x['governance'].update(baseline_tree_sha256='changed')),
])
def test_semantic_tamper_rejected_even_after_rehash(replay,artifact,mutation):
    mutate(replay,artifact,mutation)
    with pytest.raises((ValueError,KeyError)):verify(replay,pin(replay))


def test_external_pin_rejects_contract_byte_tamper(replay):
    trusted=pin(replay)
    with (replay/'hero_scenario_contract.json').open('ab') as f:f.write(b' ')
    with pytest.raises(ValueError,match='external pin'):verify(replay,trusted)


def test_artifact_symlink_refused(replay):
    p=replay/'replay/graph.json';other=replay/'outside';p.rename(other);p.symlink_to(other)
    with pytest.raises(ValueError,match='Linked'):verify(replay,pin(replay))


def test_artifact_hardlink_refused(replay):
    import os
    os.link(replay/'replay/graph.json',replay/'extra')
    with pytest.raises(ValueError,match='single-link'):verify(replay,pin(replay))


def test_public_projection_excludes_raw_host_fields():
    value=project('SourceVerification',{'id':'source:1','facts':{'concurrency_scope':'single_process_threads','private_fact':'secret'},'password':'secret','proposal_event_references':['raw'],'host_receipt':{'secret':'value'}})
    assert value=={'id':'source:1','facts':{'concurrency_scope':'single_process_threads'}}
