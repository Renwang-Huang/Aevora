"""Explicitly synthetic legacy UI fixture; no historical outcome or model claim."""
from aevora.models import utc_now


def seed_process_lock(repo):
    repo.initialize()
    created = utc_now()
    # Canonical legacy UI selector in this UUID-owned synthetic graph only.
    # No historical evidence, outcome or Agent execution is imported.
    experience = {'id': 'experience:process-local-reservation-lock', 'title': 'Synthetic process-local lock',
                  'strategy': 'shared_process_lock', 'source_type': 'synthetic_or_test_fixture',
                  'created_at': created, 'public_summary': 'UI contract fixture; no Agent execution',
                  'limitations': ['Synthetic API contract only; not historical or independently graded']}
    rule = {'id': 'rule:synthetic-ui-process-lock', 'version': '1.0.0',
            'public_description': 'Requires shared process object',
            'premises': [{'id': 'premise:synthetic-ui-topology', 'fact_key': 'concurrency_scope',
                          'allowed_values': ['single_process_threads']},
                         {'id': 'premise:synthetic-ui-object', 'fact_key': 'synchronization_scope',
                          'allowed_values': ['shared_process_object']}]}
    repo.import_experience(experience, rule)
    return experience['id']
