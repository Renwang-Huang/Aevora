import pytest
from aevora.contracts import *
from aevora.experience_resolver import resolve_v2
from aevora.models import utc_now
from tools.validation.g22_fixture import admitted,ready,proposal


def test_real_host_source_outcome_publication_and_current_reader(host):
    c,r,p=ready(host)
    assert host.repo.discover({},host.repo.state())==[]
    receipt=host.publish(p)
    assert receipt['verification']=='PUBLICATION_COMMITTED'
    assert host.head(c['id'])['state']=='PUBLISHED'
    state,rows=resolve_v2(host.repo,r['facts'],'query:real-host',utc_now())
    assert state['epoch']==1 and len(rows)==1
    assert rows[0][0]['core_verdict']=='APPLY'
    assert any(n.get('independent_run_id')==host.case['run_id'] for n in rows[0][1]['nodes'].values())
    assert host.publish(p)==receipt
    assert host.repo.state()['epoch']==1
