#!/usr/bin/env python3
"""Create project-only FalkorDB secrets outside the repository; never print them."""
import argparse
import os
from pathlib import Path
import secrets
import stat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory.absolute()
    root = Path(__file__).resolve().parents[1]
    if directory == root or root in directory.parents:
        raise ValueError('Secrets must remain outside the repository and evidence archives')
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError('Secret paths must not use symlinks')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Project secret directory must be owned by current UID and mode 0700')
    password_path = directory/'falkordb.password'
    if password_path.exists():
        info = password_path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('Existing secret must be an owned single-link mode-0600 file')
        password = password_path.read_text().strip()
        if len(password) < 32 or not password.isascii() or any(c.isspace() for c in password):
            raise ValueError('Existing secret format is invalid')
    else:
        password = secrets.token_urlsafe(48)
        descriptor = os.open(password_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as output: output.write(password+'\n')
    configuration = directory/'falkordb.conf'
    if not configuration.exists():
        descriptor = os.open(configuration, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            output.write('requirepass '+password+'\nappendonly no\nsave 60 1\ndir /data\nprotected-mode yes\n')
    else:
        info = configuration.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('Existing configuration must be an owned single-link mode-0600 file')
    print('Aevora project-only FalkorDB secret files are ready; existing files preserved.')


if __name__ == '__main__': main()
