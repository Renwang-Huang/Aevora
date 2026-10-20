from pathlib import Path
import json
import pytest
D=Path(__file__).parent
@pytest.mark.parametrize('item',['Q01','Q04','Q08','Q07','CAPACITY_EXCEEDED','EXTERNAL_UNVERIFIED','FOR_TASK','NOT_IMPLEMENTED','residual'])
def test_entry_amendment_covers_review(item):
 assert item in (D/'G21_CONTRACT_AMENDMENT_DIFF.md').read_text()
@pytest.mark.parametrize('missing',['source_sha','outcome_sha','authority_sha','expected_head_sha','request_body_sha'])
def test_q07_requires_all_pins(missing):
 assert missing in json.loads((D/'Q07_PUBLICATION_PRECONDITIONS.json').read_text())['required']

@pytest.mark.parametrize('pin',['$expected_epoch','$expected_authz_epoch','$generation','$expected_head','$prepared_sha','$prepared_json','$source_sha','$outcome_sha','$authority_sha','$candidate_sha','$manifest_sha','$prepared_chunk_pins','$expected_state_json'])
def test_q07_fence_declares_native_preconditions(pin):
    # Static contract assertion, never a production CAS or real Outcome score.
    assert pin in (D/'cypher/Q07_prepared_publication_fence.cypher').read_text()
