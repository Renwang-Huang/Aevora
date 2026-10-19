"""Public reference is exact schema, no forced decision or private inputs."""
from pathlib import Path
import json
import pytest
from integrations.aevora_v2 import write_public_contract
from aevora.contracts import schema,PROFILE

def test_native_public_contract_carries_actual_schema_and_public_vocabulary(tmp_path):
    meta={'runtime':{'topology':'multi_process_shared_sqlite','database':'sqlite'}}
    receipt=write_public_contract(tmp_path,meta);p=tmp_path/receipt['file'];body=json.loads(p.read_text())
    assert body['protocol_profile']==PROFILE
    assert body['optional_claim_context']['concurrency_scope']=='independent_processes'
    assert body['tools']['record_decision']==schema('record_decision.arguments')
    assert body['tools']['propose_experience']==schema('propose_experience.arguments')
    assert set(body['tools'])=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}
    assert all(k not in body for k in ['experience_id','decision','candidate_id','outcome','pin_root'])
    assert p.stat().st_size<=100000

def test_public_reference_never_follows_or_overwrites_a_link(tmp_path):
    target=tmp_path/'target';target.write_text('private canary')
    (tmp_path/'AEVORA_MCP_CONTRACT.json').symlink_to(target)
    with pytest.raises(OSError):write_public_contract(tmp_path,{'runtime':{}})
    assert target.read_text()=='private canary'


def test_publication_contract_explains_unknown_without_selecting_conditions(tmp_path):
    receipt=write_public_contract(tmp_path,{'runtime':{'topology':'multi_process_shared_sqlite','database':'sqlite'}})
    body=json.loads((tmp_path/receipt['file']).read_text())
    contract=body['publication_fact_contract']
    assert contract['known_task_facts']=={'task.'+k:v for k,v in body['public_declared_facts'].items()}
    assert 'task.operation_semantics' not in contract['known_task_facts']
    assert 'PENDING' in contract['unknown_condition_policy']
    assert 'rather than weakening' in contract['choice']
    assert all(x not in json.dumps(contract) for x in ['Experience:', 'Candidate:', 'reference_patch', 'guarded UPDATE'])
