"""Offline assertions about the selected live configuration; no runtime claims."""
from pathlib import Path
import os
import pytest
from integrations.codex_agent import CodexConfig, native_command
from benchmark.resources import SecurityGateError
from benchmark.runner import BenchmarkRunner


def test_gateway_command_requests_max_and_run_token_env_only():
    config=CodexConfig(Path('/synthetic/codex'),Path('/trusted/project-secret'),model='gpt-5.6-terra',provider_id='gateway',reasoning_effort='max')
    command=native_command(config,'http://127.0.0.1:9180/v1')
    assert 'model_reasoning_effort="max"' in command
    assert 'model_providers.orderflow_broker.env_key="ORDERFLOW_RUN_BROKER_TOKEN"' in command
    assert '/trusted/project-secret' not in ' '.join(command)
    assert command[-1]=='-'
    assert any(command[index:index+2]==['--enable','code_mode'] for index in range(len(command)-1))
    assert any(command[index:index+2]==['--enable','code_mode_host'] for index in range(len(command)-1))


def test_new_live_entry_rejects_legacy_without_a_security_downgrade():
    with pytest.raises(SecurityGateError,match='BLOCKED_SECURITY_GATE'):
        CodexConfig.from_environment(provider_id='legacy')


@pytest.mark.parametrize('kind',['hardlink','fifo','parent_symlink'])
def test_manual_patch_boundary_rejects_unsafe_original_file(tmp_path,monkeypatch,kind):
    import evaluator.runner as evaluator
    good=tmp_path/'source.diff';good.write_text('--- a/app/service.py\n+++ b/app/service.py\n@@ -1 +1 @@\n-a\n+b\n')
    unsafe=tmp_path/'unsafe.diff'
    if kind=='hardlink':os.link(good,unsafe)
    elif kind=='fifo':os.mkfifo(unsafe)
    else:
        directory=tmp_path/'linked';directory.symlink_to(tmp_path,target_is_directory=True);unsafe=directory/'source.diff'
    calls=[]
    monkeypatch.setattr(evaluator,'evaluate',lambda *a,**k:calls.append(True))
    report=BenchmarkRunner(tmp_path/'runs').evaluate('A',unsafe)
    assert calls==[]
    assert report['overall_status']=='ERROR'
    assert report['submission_integrity_status']=='ERROR'
