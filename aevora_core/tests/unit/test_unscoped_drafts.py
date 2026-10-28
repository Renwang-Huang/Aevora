from aevora.candidate import validate_proposal
from aevora.proposal_contract import CandidateProposal


def test_unscoped_observations_are_valid_untrusted_drafts():
    draft = dict(candidate_key='ui-observation', title='Synthetic UI observation',
                 strategy='Explain empty states', public_summary='Draft contract test',
                 necessary_conditions={}, inapplicable_conditions={}, scope={},
                 unknown_fields=[], limitations=['Scope is not established'], source_references=[])
    assert CandidateProposal.model_validate(draft).model_dump(exclude_none=True) == validate_proposal(draft)
    schema = CandidateProposal.model_json_schema()
    assert schema['properties']['necessary_conditions'].get('minProperties', 0) == 0
    assert schema['properties']['scope'].get('minProperties', 0) == 0
