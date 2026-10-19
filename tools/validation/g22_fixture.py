"""Owned Host acceptance helpers. Real Oracle cases, not an Agent score."""
from aevora.contracts import digest

def proposal(key='principle'):
    return dict(candidate_key=key,title='Atomic reservation',strategy='Reserve stock with an atomic transaction',
                public_summary='A transaction protects the read and reservation ledger.',
                necessary_conditions={'task.shared_state_kind':['sqlite_file']},
                inapplicable_conditions={},scope={'task.shared_state_kind':['sqlite_file']},
                unknown_fields=[],limitations=['Host-controlled candidate; causal benefit UNKNOWN'],source_references=[])

def admitted(h,key='principle',p=None):
    p=p or proposal(key)
    c=h.propose(p,run_id=h.case['run_id'],tree_sha=h.case['tree_sha'])
    s=h.verify_source(c['id'],h.verifier.authority_id,'evaluation_report.json')
    o=h.verify_outcome(c['id'],s['id'])
    r=h.review(c['id'],s['id'],o['id'],approved_scope=p['scope'],reason='Independent Oracle verified; bounded engineering review')
    return c,s,o,r

def ready(h,key='principle',**kwargs):
    c,s,o,r=admitted(h,key)
    head=h.transition(c['id'],'PUBLISHING',expected_head=digest(h.head(c['id'])),reason='Prepare immutable publication')
    prep=h.prepare(c['id'],r['id'],request_key=key,expected_head=digest(head),expected_epoch=h.repo.state()['epoch'],**kwargs)
    return c,r,prep
