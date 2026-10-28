"""Untrusted file/policy rejection; no database, private package or model."""
from copy import deepcopy
import subprocess
import sys
import pytest
from aevora.project_source import POLICY_VERSION, load_policy, validate_policy
from aevora.source_evidence import OutcomeVerificationError, read_junit


def policy():
    return {'schema_version':POLICY_VERSION,'verifier_id':'independent-ci',
        'origin':'independent_project','suite_sha256':'a'*64,'evaluator_sha256':'b'*64,
        'required_tests':['test_one::test_contract'],'facts':{'contract_version':'v1'}}


@pytest.mark.parametrize('key,value',[
    ('origin','natural_agent_run'),('origin','external_unverified'),
    ('required_tests',[]),('required_tests',['same::test','same::test']),
    ('required_tests',['test_without_classname']),('facts',{'private_fact':'secret'}),
    ('suite_sha256','not-a-pin'),('verifier_id','../untrusted'),
])
def test_invalid_trust_policy_rejected(key,value):
    p=policy();p[key]=value
    with pytest.raises(ValueError): validate_policy(p)


def test_junit_classname_is_part_of_required_identity():
    xml=b'<testsuite tests="1"><testcase classname="other" name="test_contract"/></testsuite>'
    with pytest.raises(OutcomeVerificationError): read_junit(xml,policy()['required_tests'],identity='nodeid')


@pytest.mark.parametrize('xml',[
    b'<!DOCTYPE x><testsuite/>',
    b'<testsuite tests="2"><testcase classname="test_one" name="test_contract"/></testsuite>',
    b'<testsuite><testcase classname="test_one" name="test_contract"/><testcase classname="test_one" name="test_contract"/></testsuite>',
    b'<testsuite><testcase classname="test_one" name="test_contract" time="nan"/></testsuite>',
])
def test_junit_cannot_invent_a_complete_pass(xml):
    with pytest.raises(ValueError): read_junit(xml,policy()['required_tests'],identity='nodeid')


def test_policy_needs_protected_host_directory(tmp_path):
    import json
    path=tmp_path/'policy.json';path.write_text(json.dumps(policy()));path.chmod(0o600)
    tmp_path.chmod(0o700);assert load_policy(path)==policy()
    tmp_path.chmod(0o755)
    with pytest.raises(OutcomeVerificationError): load_policy(path)
    tmp_path.chmod(0o700);path.chmod(0o644)
    with pytest.raises(OutcomeVerificationError): load_policy(path)


def test_public_project_adapter_imports_no_orderflow_or_private_package():
    code="import sys,aevora.project_source,aevora.project_receipt; assert not any(n.startswith(('benchmark','evaluator','integrations','aevora_maintainer','aevora.orderflow')) for n in sys.modules)"
    result=subprocess.run([sys.executable,'-I','-c',code],capture_output=True)
    assert result.returncode==0,result.stderr.decode()
