"""Local backend write fencing shared by native Host and legacy entrypoints.

Unmanaged writes take a transient shared enrollment barrier. Once bound by a
Host, writers require exclusive ownership until repository close. This keeps
independent unmanaged graph/concurrency tests valid without a bypass switch.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import pwd
import stat
import sys

from .host_config import private_directory, read_private_json
from .startup import StartupError


def backend_id(host, port, graph):
    if host == 'localhost':
        host = '127.0.0.1'
    return hashlib.sha256(f'falkordb/{host}/{port}/{graph}'.encode()).hexdigest()


def registry_directory(identity):
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        raise StartupError('HOST_ACCOUNT_REQUIRED',
            'The Host UID has no registered OS account and verified home directory.',
            'Use a registered Host account; container images must create their runtime user. HOME/XDG overrides do not establish ownership.') from None
    base = home / ('Library/Application Support' if sys.platform == 'darwin' else '.local/state')
    if not base.is_absolute():
        raise ValueError('Absolute state home required')
    return base / 'aevora/backends' / identity


class BackendGuard:
    def __init__(self, host, port, graph):
        self.identity = backend_id(host, port, graph)
        self.directory = registry_directory(self.identity)
        self.fd = None

    def _open(self):
        private_directory(self.directory, create=True)
        path = self.directory / 'writer.lock'
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            os.close(fd)
            raise ValueError('Protected backend lock required')
        return fd

    def _inherited(self):
        selected = os.environ.get('AEVORA_BACKEND_LOCK_FD')
        if selected is None:
            return None
        original = int(selected)
        actual = self._open()
        try:
            a, b = os.fstat(original), os.fstat(actual)
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                raise ValueError('Inherited ownership does not match backend')
            # A different open-file description cannot acquire this while the
            # Host owns it. The inherited description keeps ownership alive.
            fcntl.flock(original, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return os.dup(original)
        finally:
            os.close(actual)

    @contextmanager
    def write(self):
        if self.fd is not None:
            yield
            return
        fd = None
        try:
            try:
                fd = self._inherited()
                if fd is not None:
                    binding = read_private_json(self.directory / 'binding.json', 4096)
                    if binding.get('backend_id') != self.identity:
                        raise ValueError('Backend binding mismatch')
                    self.fd, fd = fd, None
                else:
                    fd = self._open()
                    bound = (self.directory / 'binding.json').exists()
                    fcntl.flock(fd, (fcntl.LOCK_EX if bound else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                    if bound:
                        binding = read_private_json(self.directory / 'binding.json', 4096)
                        if binding.get('schema_version') != 'aevora.backend-binding/1' or binding.get('backend_id') != self.identity:
                            raise ValueError('Backend binding mismatch')
                        self.fd, fd = fd, None
            except BlockingIOError:
                raise StartupError('AEVORA_BACKEND_ALREADY_OWNED',
                    'Another Host owns this managed backend; no legacy write was dispatched.',
                    'Stop its Host and use an exclusive maintenance window; a different session root does not grant write access.') from None
            yield
        finally:
            if fd is not None:
                os.close(fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
