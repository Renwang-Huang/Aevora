"""Public checks requiring no maintainer package, hidden tests or model key."""
import json
import pytest
from aevora.demo import state_path, read_state
from aevora.demo_verify import verify


def test_actual_public_sqlite_verifier():
    result=verify()
    assert result['verdict']=='PASS'
    assert result['available']+result['reservations']==result['initial_stock']
    assert result['model_execution'] is False
    assert result['independent_orderflow_oracle'] is False

@pytest.mark.parametrize('stage',['private','../baseline','', 'before/after'])
def test_state_selector_is_closed(tmp_path,stage):
    with pytest.raises(ValueError):state_path(tmp_path,stage)

def test_state_file_rejects_link(tmp_path):
    target=tmp_path/'original';target.write_text('{}');(tmp_path/'baseline.json').symlink_to(target)
    with pytest.raises(OSError):read_state(tmp_path,'before')

def test_state_file_rejects_public_permissions(tmp_path):
    p=tmp_path/'baseline.json';p.write_text('{}');p.chmod(0o644)
    with pytest.raises(ValueError):read_state(tmp_path,'before')


def test_seed_rejects_link_before_changing_target(tmp_path):
    from aevora.demo import seed
    target=tmp_path/'real';target.mkdir(mode=0o755)
    link=tmp_path/'linked';link.symlink_to(target,target_is_directory=True)
    before=target.stat().st_mode
    with pytest.raises(ValueError,match='links'):seed(link)
    assert target.stat().st_mode==before and list(target.iterdir())==[]

def test_seed_rejects_existing_nonprivate_directory(tmp_path):
    from aevora.demo import seed
    directory=tmp_path/'public';directory.mkdir(mode=0o755)
    with pytest.raises(ValueError,match='mode0700'):seed(directory)
    assert directory.stat().st_mode&0o777==0o755
