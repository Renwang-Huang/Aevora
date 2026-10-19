"""Synthetic contracts for archival; never evidence of real agent execution."""
import json
from pathlib import Path
import pytest
from integrations.runtime_evidence import archive_native_rollouts
from integrations.codex_agent import CodexConfig, native_command
from benchmark.resources import PARTICIPANT_LIMITS


def test_gateway_fresh_state_supports_native_fork_without_ephemeral():
    config = CodexConfig(Path('/tools/codex'), Path('/private/key'), 'gpt-5.6-terra', provider_id='gateway', reasoning_effort='max')
    command = native_command(config, 'http://127.0.0.1:9180/v1')
    assert '--ephemeral' not in command
    assert '--resume' not in command
    assert 'code_mode' in command and 'code_mode_host' in command and 'code_mode_only' in command
    assert PARTICIPANT_LIMITS.address_space_bytes == 2 * 1024**4
    assert PARTICIPANT_LIMITS.memory_bytes == 2 * 1024**3
    assert PARTICIPANT_LIMITS.max_tasks == 768


def test_native_rollout_archives_real_bytes_except_secret(tmp_path):
    state = tmp_path/'state'; archive = tmp_path/'archive'; archive.mkdir()
    sessions = state/'sessions'/'2026'; sessions.mkdir(parents=True)
    record = {'type': 'session_meta', 'payload': {'id': 'synthetic-child', 'parent_id': 'synthetic-parent'}}
    source = sessions/'rollout.jsonl'
    source.write_text(json.dumps(record)+'\n'+json.dumps({'type': 'response_item', 'payload': {'secret': 'not-a-real-credential'}})+'\n')
    result = archive_native_rollouts(state, archive, secret_values=('not-a-real-credential',))
    assert result['availability'] == 'AVAILABLE'
    item = result['files'][0]
    assert item['session_metadata'] == [record['payload']]
    assert item['line_count'] == 2 and item['redacted_lines'] == 1
    assert 'not-a-real-credential' not in Path(item['path']).read_text()
    with pytest.raises(FileExistsError):
        archive_native_rollouts(state, archive)


@pytest.mark.parametrize('variant', ['file_symlink', 'directory_symlink', 'hardlink', 'fifo'])
def test_native_rollout_refuses_unsafe_entries(tmp_path, variant):
    import os
    state = tmp_path/'state'; archive = tmp_path/'archive'; archive.mkdir()
    sessions = state/'sessions'; sessions.mkdir(parents=True)
    external = tmp_path/'other.jsonl'; external.write_text('{}\n')
    if variant == 'file_symlink':
        (sessions/'unsafe.jsonl').symlink_to(external)
    elif variant == 'directory_symlink':
        (sessions/'unsafe').symlink_to(tmp_path, target_is_directory=True)
    elif variant == 'hardlink':
        os.link(external, sessions/'unsafe.jsonl')
    else:
        os.mkfifo(sessions/'unsafe.jsonl')
    with pytest.raises(ValueError):
        archive_native_rollouts(state, archive)
    assert external.read_text() == '{}\n'


def test_native_rollout_missing_is_unavailable(tmp_path):
    assert archive_native_rollouts(tmp_path/'state', tmp_path/'archive')['availability'] == 'UNAVAILABLE'


def test_native_rollout_budget_is_finite(tmp_path):
    state=tmp_path/'state'; sessions=state/'sessions'; sessions.mkdir(parents=True)
    with (sessions/'oversized.jsonl').open('wb') as output:
        output.truncate(64*1024**2+1)
    with pytest.raises(ValueError, match='budget'):
        archive_native_rollouts(state, tmp_path/'archive')


def test_native_rollout_deep_json_is_controlled_error(tmp_path):
    sessions=tmp_path/'state'/'sessions'; sessions.mkdir(parents=True)
    (sessions/'deep.jsonl').write_text('['*10000+'0'+']'*10000+'\n')
    with pytest.raises(ValueError, match='nesting'):
        archive_native_rollouts(tmp_path/'state', tmp_path/'archive')


def test_native_rollout_counts_all_entries(tmp_path, monkeypatch):
    import os
    sessions=tmp_path/'state'/'sessions'; sessions.mkdir(parents=True)
    monkeypatch.setattr(os, 'walk', lambda *a, **k: [(str(sessions), [], ['irrelevant']*10001)])
    with pytest.raises(ValueError, match='entry/depth'):
        archive_native_rollouts(tmp_path/'state', tmp_path/'archive')
