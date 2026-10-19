"""Opt-in adapter contracts; these tests are not native model evidence."""
import json
from pathlib import Path
import socket
import pytest

from benchmark.participant_sandbox import participant_command
from benchmark.resources import SecurityGateError
from integrations.codex_agent import CodexConfig, native_command


def config(**kwargs):
    return CodexConfig(Path('/tools/codex'), Path('/maintainer/gateway.key'),
                       provider_id='gateway', model='gpt-5.6-terra', reasoning_effort='max', **kwargs)


def overrides(command):
    return {command[n+1].split('=', 1)[0]: command[n+1].split('=', 1)[1]
            for n, value in enumerate(command[:-1]) if value == '-c'}


def test_default_preserves_disabled_interface():
    value = config()
    assert value.experience_mode == 'disabled'
    assert not any(key.startswith('mcp_servers.aevora') for key in overrides(native_command(value, 'http://127.0.0.1:9180/v1')))


def test_optin_native_tools_are_exact_and_no_secret_is_in_configuration():
    value = config(experience_mode='aevora', completion_policy='completion-aware', timeout_seconds=None, request_budget=None)
    command = native_command(value, 'http://127.0.0.1:9180/v1')
    fields = overrides(command)
    assert json.loads(fields['mcp_servers.aevora.enabled_tools']) == ['resolve_experience', 'build_evidence_bundle', 'record_decision']
    assert json.loads(fields['mcp_servers.aevora.env_vars']) == ['AEVORA_RUN_TOKEN', 'AEVORA_RUN_ID']
    assert fields['mcp_servers.aevora.required'] == 'true'
    assert fields['mcp_servers.aevora.default_tools_approval_mode'] == '"auto"'
    assert value.timeout_seconds is None and value.request_budget is None
    assert '/maintainer/gateway.key' not in ' '.join(command)
    assert 'submit_outcome' not in ' '.join(command)


def test_optin_rejects_legacy_boundary():
    with pytest.raises(SecurityGateError):
        CodexConfig(Path('/tools/codex'), Path('/unused'), experience_mode='aevora')


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError, match='Unknown Experience'):
        config(experience_mode='invented')


def test_mount_requires_socket_and_proxy_pair(tmp_path):
    workspace = tmp_path/'workspace'; workspace.mkdir()
    state = tmp_path/'state'; state.mkdir()
    with pytest.raises(ValueError, match='both'):
        participant_command(workspace, state, Path('/usr/bin/python3.12'), ['true'], aevora_socket=tmp_path/'sock')


def test_mount_is_one_readonly_scoped_socket_and_one_proxy(tmp_path):
    workspace = tmp_path/'workspace'; workspace.mkdir()
    state = tmp_path/'state'; state.mkdir()
    proxy = tmp_path/'proxy.py'; proxy.write_text('# contract fixture\n')
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    path = tmp_path/'mcp.sock'; channel.bind(str(path))
    try:
        command = participant_command(workspace, state, Path('/usr/bin/python3.12'), ['true'],
                                      aevora_socket=path, aevora_proxy=proxy)
        assert '--unshare-net' in command
        assert command[command.index(str(path))-1:command.index(str(path))+2] == ['--ro-bind', str(path), '/aevora-channel/mcp.sock']
        assert command[command.index(str(proxy))-1:command.index(str(proxy))+2] == ['--ro-bind', str(proxy), '/aevora_mcp_proxy.py']
        assert not any('falkordb.password' in part or '/maintainer' in part for part in command)
    finally:
        channel.close()


def test_governance_fingerprint_binds_code_and_real_sdk_versions():
    from integrations.aevora import runtime_fingerprints
    value = runtime_fingerprints()
    for name in ('mcp_server', 'mcp_broker', 'mcp_proxy', 'graph_repository', 'experience_resolver', 'feedback', 'orderflow_outcome_bridge'):
        assert len(value['files_sha256']['aevora/'+name+'.py']) == 64
    assert len(value['files_sha256']['integrations/aevora.py']) == 64
    assert value['packages']['aevora-core'] == '0.1.0'
    assert value['packages']['mcp'] == '1.26.0'
    assert value == runtime_fingerprints()
