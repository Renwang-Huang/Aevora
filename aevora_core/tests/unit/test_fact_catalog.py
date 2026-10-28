import pytest
from aevora.fact_catalog import catalog, support_coverage
from aevora.models import InvalidRecord, normalize_context, validate_scope
from aevora.candidate import candidate_checklist, validate_proposal
from aevora.proposal_contract import CandidateProposal


def test_native_coverage_does_not_require_unrelated_concurrency_but_legacy_keeps_it():
    assert support_coverage({'runtime_engine'}) == {'runtime_engine', 'storage_backend'}
    assert support_coverage({'shared_state_kind'}) == {'shared_state_kind', 'concurrency_scope'}
    assert support_coverage({'runtime_engine', 'shared_state_kind'}) == {
        'runtime_engine', 'storage_backend', 'shared_state_kind', 'concurrency_scope'}
    assert catalog()['registration'] == 'RELEASE_CONTROLLED_NOT_AGENT_DEFINED'


def test_native_values_are_typed_and_unknown_stays_unknown():
    for value in (False, 'invented'):
        with pytest.raises(InvalidRecord):
            normalize_context({'runtime_engine': value})
    assert normalize_context({'runtime_engine': None}) == {'runtime_engine': None}
    assert validate_scope({'storage_backend': ['sqlite']}) == {'storage_backend': ['sqlite']}
    with pytest.raises(InvalidRecord):
        validate_scope({'storage_backend': ['invented']})


def test_target_facts_are_separate_from_host_and_require_project_support():
    assert support_coverage({'target_revision'}) == {'target_revision', 'target_project'}
    assert normalize_context({'target_project': 'demo', 'target_revision': 'a' * 40,
                              'target_branch': 'feat/recall'})['target_project'] == 'demo'
    for bad in ({'target_revision': 'unknown-commit'}, {'target_project': False},
                {'target_project': '/private/workspace'}):
        with pytest.raises(InvalidRecord):
            normalize_context(bad)
    assert normalize_context({'target_revision': None}) == {'target_revision': None}


def test_lineage_is_public_declaration_and_not_admission():
    body = dict(candidate_key='bounded', title='Runtime observation', strategy='Inspect provenance',
                public_summary='Explicit grammar test', necessary_conditions={'runtime_engine':['go_native']},
                inapplicable_conditions={}, scope={'storage_backend':['sqlite']}, unknown_fields=[],
                limitations=['No independent source'], source_references=[],
                derived_from_candidate_id='candidate:run:original')
    assert CandidateProposal.model_validate(body).model_dump(exclude_none=True) == validate_proposal(body)
    result = candidate_checklist(body, 'PROPOSED')
    assert result['authority'] == 'UNTRUSTED_DECLARATION'
    assert result['next_action'] == 'REQUEST_EVIDENCE_REVIEW'
    assert result['causal_benefit'] == 'UNKNOWN'
    body['scope'] = {'shared_state_kind':['/home/private-path-marker']}
    with pytest.raises(InvalidRecord):
        validate_proposal(body)
