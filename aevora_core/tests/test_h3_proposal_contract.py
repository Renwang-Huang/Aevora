"""Official SDK schema, real graph call and rejection of natural-run bad shapes."""
import asyncio
import pytest
from pydantic import ValidationError
from test_h3_lifecycle import life,proposal,FACTS
from aevora.proposal_contract import CandidateProposal
from aevora.mcp_server import create_server,ExperienceService


def test_sdk_exposes_actual_object_condition_schema(life):
    server=create_server(ExperienceService(run_id='schema-run',public_context=FACTS,repository=life.repo,enable_proposals=True))
    tools=asyncio.run(server.list_tools());tool=next(t for t in tools if t.name=='propose_experience')
    definition=tool.inputSchema['$defs']['CandidateProposal']
    for key in ['necessary_conditions','inapplicable_conditions','scope']:
        assert definition['properties'][key]['type']=='object'
    assert definition['additionalProperties'] is False
    assert 'concurrency_scope' in definition['properties']['unknown_fields']['items']['enum']
    assert {t.name for t in tools}=={'resolve_experience','build_evidence_bundle','record_decision','propose_experience'}


def test_original_narrative_array_input_remains_rejected():
    p=proposal();p['necessary_conditions']=['A sentence cannot replace factual scope']
    with pytest.raises(ValidationError):CandidateProposal.model_validate(p)
    p=proposal();p['unknown_fields']=['SQLite journal mode in the environment']
    with pytest.raises(ValidationError):CandidateProposal.model_validate(p)


def test_typed_proposal_roundtrip_preserves_boolean_and_actual_graph(life):
    p=proposal();p['scope']['worker_count_known']=[True]
    parsed=CandidateProposal.model_validate(p).model_dump()
    assert parsed==p and type(parsed['scope']['worker_count_known'][0]) is bool
    result=life.propose('typed-run',parsed)
    assert life.inspect(result['candidate_id'])['candidate']['body']==p
    assert life.repo.experience_ids()==[]
