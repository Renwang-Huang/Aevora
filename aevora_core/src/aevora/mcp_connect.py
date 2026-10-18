"""Ordinary developer stdio connector for an explicitly configured Host grant.

This consumer receives one short-lived capability, never a database password.
The fixed-path Participant proxy stays unchanged. This local same-UID connector
does not claim to isolate an adversarial Agent from its owner's entire account.
Use the physically isolated runtime for untrusted benchmark participants.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import stat
import sys


def read_grant(path):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Linked grant path refused')
    parent=path.parent.stat()
    if parent.st_uid!=os.getuid() or stat.S_IMODE(parent.st_mode)!=0o700:
        raise ValueError('Owned mode0700 grant directory required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1 or not 1<=s.st_size<=4096:
            raise ValueError('Owned bounded mode0600 single-link grant required')
        data=os.read(fd,4097)
    finally:os.close(fd)
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate grant key')
            d[k]=v
        return d
    value=json.loads(data,object_pairs_hook=pairs)
    if value.get('transport')!='aevora-mcp-uds-v1':raise ValueError('Unknown grant transport')
    if set(value)-{'AEVORA_RUN_ID','AEVORA_RUN_TOKEN','socket','consumer_socket','transport','expires_at'}:
        raise ValueError('Unexpected grant properties')
    socket_path=Path(value['socket'])
    if not socket_path.is_absolute() or socket_path.parent!=path.parent or socket_path.is_symlink():
        raise ValueError('Grant socket must be an ordinary sibling in the private runtime directory')
    if value.get('expires_at'):
        expiry=datetime.fromisoformat(value['expires_at'].replace('Z','+00:00'))
        if expiry.tzinfo is None or expiry<=datetime.now(timezone.utc):raise ValueError('Grant expired')
    return value


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capability-file',type=Path,required=True);args=p.parse_args(argv)
    try:
        grant=read_grant(args.capability_file)
        # The ordinary connector cannot be a DB client; strip any mistakenly
        # inherited database settings before starting the stdlib byte proxy.
        for key in list(os.environ):
            if key.startswith('AEVORA_FALKORDB_'):os.environ.pop(key)
        os.environ['AEVORA_RUN_ID']=grant['AEVORA_RUN_ID'];os.environ['AEVORA_RUN_TOKEN']=grant['AEVORA_RUN_TOKEN']
        from . import mcp_proxy
        mcp_proxy.SOCKET_PATH=grant['socket'];del grant
        return mcp_proxy.main()
    except (ValueError,KeyError,TypeError,OSError):
        sys.stderr.write('Aevora scoped connection unavailable or revoked.\n');return 1


if __name__=='__main__':raise SystemExit(main())
