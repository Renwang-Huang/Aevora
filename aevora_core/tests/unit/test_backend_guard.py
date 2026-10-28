import fcntl
import json
import os

import pytest

from aevora.backend_guard import BackendGuard
from aevora.startup import StartupError


def test_enrollment_barrier_and_bound_exclusive_writer(tmp_path, monkeypatch):
    monkeypatch.setattr('aevora.backend_guard.registry_directory', lambda identity: tmp_path / identity)
    a = BackendGuard('127.0.0.1', 17790, 'test')
    b = BackendGuard('127.0.0.1', 17790, 'test')
    with a.write(), b.write():
        fd = a._open()
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    path = a.directory / 'binding.json'
    path.write_text(json.dumps({'schema_version': 'aevora.backend-binding/1', 'backend_id': a.identity, 'root': str(tmp_path)}))
    path.chmod(0o600)
    try:
        with a.write():
            with pytest.raises(StartupError, match='Another Host'):
                with b.write():
                    pytest.fail('second writer admitted')
    finally:
        a.close()
        b.close()


def test_worker_cannot_claim_an_unrelated_inherited_file(tmp_path, monkeypatch):
    monkeypatch.setattr('aevora.backend_guard.registry_directory', lambda identity: tmp_path / identity)
    other = tmp_path / 'unrelated'
    other.write_text('')
    with other.open('r') as f:
        monkeypatch.setenv('AEVORA_BACKEND_LOCK_FD', str(f.fileno()))
        guard = BackendGuard('127.0.0.1', 17790, 'test')
        with pytest.raises(ValueError, match='does not match'):
            with guard.write():
                pytest.fail('foreign ownership admitted')


def test_unregistered_host_account_cannot_use_home_override(tmp_path, monkeypatch):
    def missing(_):
        raise KeyError('synthetic missing OS account')
    monkeypatch.setattr('aevora.backend_guard.pwd.getpwuid', missing)
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(StartupError) as error:
        BackendGuard('127.0.0.1', 17790, 'test')
    assert error.value.code == 'HOST_ACCOUNT_REQUIRED'
