"""Owned local session directories around the existing official MCP broker.

current.json is a mutable selector, never evidence or a grant. Each session's
manifest and raw events are exclusive files and remain after shutdown/crash.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import uuid
from .host_config import private_directory, read_private_json
from .models import utc_now, validate_id
from .startup import StartupError

SCHEMA = 'aevora.local-session/1'


def current_session(root, *, required=True):
    root = private_directory(root)
    try: value = read_private_json(root/'current.json', 4096)
    except FileNotFoundError:
        if not required: return None
        raise StartupError('SESSION_NOT_STARTED', 'No current MCP session is recorded.', 'Start aevora serve in the Host terminal, then reconnect the client.') from None
    except StartupError: raise
    except (OSError, ValueError, TypeError):
        raise StartupError('SESSION_SELECTOR_INVALID', 'Current session selector is invalid.', 'Check the owned session root; preserve session evidence and choose another root if recovery is needed.') from None
    try:
        if not isinstance(value,dict) or set(value) != {'schema_version','directory','run_id'} or value['schema_version'] != SCHEMA: raise ValueError()
        if not re.fullmatch(r's-[a-f0-9]{16}', value['directory']): raise ValueError()
        validate_id(value['run_id'])
    except (ValueError,TypeError,KeyError):
        raise StartupError('SESSION_SELECTOR_INVALID', 'Current session selector is invalid.', 'Check the owned session root; preserve session evidence and choose another root if recovery is needed.') from None
    folder = private_directory(root/value['directory'])
    return {**value, 'path':folder, 'capability':folder/'grant.json', 'events':folder/'mcp_events.jsonl'}


class SessionLease:
    def __init__(self, root, args):
        self.root, self.args, self.fd = Path(root).absolute(), args, None

    def __enter__(self):
        self.root = private_directory(self.root, create=True)
        try: self.fd = os.open(self.root/'.owner.lock', os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC, 0o600)
        except OSError:
            raise StartupError('SESSION_LOCK_UNAVAILABLE', 'The session ownership lock could not be opened safely.', 'Check the owned session root permissions and ordinary lock file; preserve evidence or select another root.') from None
        try:
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise StartupError('SESSION_LOCK_INVALID', 'The session ownership lock is not a protected ordinary file.', 'Check the session root or choose another owned root; preserve existing evidence.')
            try: fcntl.flock(self.fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                raise StartupError('SESSION_ALREADY_RUNNING', 'An MCP Host already owns this session root.', 'Use the existing Host and reconnect, or stop it normally before repeating this command. For a parallel task choose another --session-root.') from None
            name = 's-'+uuid.uuid4().hex[:16]
            folder = self.root/name
            if len(os.fsencode(folder/'mcp.sock')) > 107:
                raise StartupError('SESSION_PATH_TOO_LONG', 'The session socket path exceeds the Unix socket limit.', 'Configure a shorter absolute --session-root outside source and evidence archives.')
            folder.mkdir(mode=0o700)
            self.args.run_id = self.args.run_id or 'local-'+uuid.uuid4().hex
            self.args.socket, self.args.capability_file, self.args.events = map(str, [folder/'mcp.sock',folder/'grant.json',folder/'mcp_events.jsonl'])
            self.args._session_root = str(self.root)
            self.args._on_ready = lambda: self.publish(name)
            manifest_fd = os.open(folder/'session.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(manifest_fd,'w') as out:
                json.dump({'schema_version':SCHEMA,'run_id':self.args.run_id,'created_at':utc_now(),
                    'events':'mcp_events.jsonl','scope':'Local Host channel; native identity unavailable'},out)
            return self.args
        except BaseException:
            self.close()
            raise

    def publish(self, name):
        target = self.root/'current.json'
        if target.exists() or target.is_symlink(): read_private_json(target, 4096)
        temporary = self.root/('.current-'+uuid.uuid4().hex+'.json')
        try:
            fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as out:
                json.dump({'schema_version':SCHEMA,'directory':name,'run_id':self.args.run_id},out)
            os.replace(temporary,target)
        finally: temporary.unlink(missing_ok=True)

    def close(self):
        if self.fd is not None: os.close(self.fd); self.fd = None

    def __exit__(self, *_): self.close()
