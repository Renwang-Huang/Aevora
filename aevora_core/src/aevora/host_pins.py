"""Read-only OS-rooted v2 trust pins. Never an MCP registration capability.

The private Host writes single-link immutable files before graph activation.
Prepared pins confer no visibility: the reader still requires graph COMMITS,
epoch, complete catalogue and witness. Each lookup reads the current bytes;
there is no permission or negative-evidence cache.
"""
from collections.abc import Mapping
from pathlib import Path
import os
import stat
from .contracts import TrustRegistry, canonical_json, decode_json, digest, require


class PinMap(Mapping):
    def __init__(self, root, category):
        self.root = Path(root)
        self.category = category

    def _open_root(self):
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.root.absolute().parts[1:]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            s = os.fstat(fd)
            require(s.st_uid == os.getuid() and stat.S_IMODE(s.st_mode) == 0o700, 'UNAUTHORIZED')
            return fd
        except BaseException:
            os.close(fd)
            raise

    def __getitem__(self, key):
        fd = self._open_root()
        name = digest([self.category, key]) + '.json'
        try:
            try:
                f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            except FileNotFoundError:
                raise KeyError(key) from None
            try:
                before = os.fstat(f)
                require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                        and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                        and before.st_size <= 4096, 'UNAUTHORIZED')
                raw = os.read(f, 4097)
                after = os.fstat(f)
                require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                        (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and len(raw) == before.st_size <= 4096)
                value = decode_json(raw)
                require(value['category'] == self.category and value['key'] == key
                        and raw == canonical_json(value).encode())
                return value['value']
            finally:
                os.close(f)
        finally:
            os.close(fd)

    def __iter__(self):
        raise TypeError('Host pins are lookup-only; no public enumeration')

    def __len__(self):
        raise TypeError('Host pins are lookup-only')


def read_registry(root):
    return TrustRegistry(**{k: PinMap(root, k) for k in
                            ('authorities', 'outcomes', 'fact_sources', 'publications')})
