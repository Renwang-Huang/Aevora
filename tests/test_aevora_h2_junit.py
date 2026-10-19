"""Synthetic XML negative controls; not engineering outcomes or native runs."""
from pathlib import Path
import pytest
from scripts.aevora_h2_junit import check_junit


@pytest.mark.parametrize('body,attributes,status', [
    ('<testcase classname="x" name="a"/>', 'tests="1"', 'PASS'),
    ('<testcase classname="x" name="a"><skipped/></testcase>', 'tests="1"', 'FAIL'),
    ('<testcase classname="x" name="a"><failure/></testcase>', 'tests="1"', 'FAIL'),
    ('<testcase classname="x" name="a"><error/></testcase>', 'tests="1"', 'FAIL'),
    ('<testcase classname="x" name="a"/><testcase classname="x" name="a"/>', 'tests="2"', 'FAIL'),
    ('<testcase classname="x" name="other"/>', 'tests="1"', 'FAIL'),
    ('<testcase classname="x" name="a"/>', 'tests="0"', 'FAIL'),
    ('', 'tests="0"', 'FAIL'),
])
def test_independent_junit_gate(tmp_path,body,attributes,status):
    p=tmp_path/'junit.xml';p.write_text(f'<testsuites><testsuite {attributes}>{body}</testsuite></testsuites>')
    assert check_junit(p,['x::a'])['status']==status


@pytest.mark.parametrize('required',[[],['x::a','x::a']])
def test_identity_authority_is_required(tmp_path,required):
    p=tmp_path/'junit.xml';p.write_text('<testsuite/>')
    with pytest.raises(ValueError):check_junit(p,required)
