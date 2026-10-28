"""Public Core broker lifecycle, independent of the Benchmark Registry/Oracle.

Host holds DB credentials; consumer only receives a scoped capability. Run this
in a trusted host account outside the consumer's namespaces. The generated
capability is private runtime state and MUST NOT be placed in an evidence ZIP.
"""
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import time
from datetime import datetime,timedelta,timezone
from .models import normalize_context
from .mcp_broker import MCPBroker
from .host_config import private_directory
from .startup import StartupError


def serve(args, repo):
    from .cli import read_json
    context = normalize_context(read_json(args.context) if args.context else getattr(args,'_public_context',{}))
    capability = Path(args.capability_file)
    private_directory(capability.parent)
    paths = [Path(args.socket),capability,Path(args.events)]
    if any(not p.is_absolute() for p in paths) or Path(args.socket).parent != capability.parent:
        raise StartupError('SESSION_PATHS_INVALID', 'Grant and socket must be absolute siblings in the private session directory.', 'Use managed aevora serve, or provide fresh absolute legacy paths.')
    if any(p.exists() or p.is_symlink() for p in paths):
        raise StartupError('SESSION_PATH_EXISTS', 'An explicit socket, grant or event path already exists; nothing was overwritten.', 'Stop any active Host normally. Start aevora serve with a profile/--session-root for automatic fresh sessions, or choose fresh explicit paths. Preserve old events.')
    ttl=getattr(args,'capability_ttl',None)
    if ttl is not None and (type(ttl) is not int or not 1<=ttl<=86400):
        raise StartupError('CAPABILITY_TTL_INVALID', 'Explicit capability TTL must be 1..86400 seconds.', 'Omit --capability-ttl to bind the grant to the Host lifetime, or choose a bounded duration.')
    # Confirm real availability before granting a channel. Empty graph is valid.
    repo.state_fingerprint()
    stopped = threading.Event()
    previous = {}
    def stop(*_): stopped.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, stop)
    token = secrets.token_urlsafe(32)
    expires=time.monotonic()+ttl if ttl is not None else None
    try:
        with MCPBroker(run_id=args.run_id, public_context=context, socket_path=Path(args.socket), run_token=token,
                event_path=Path(args.events), enable_proposals=args.enable_proposals) as broker:
            fd = os.open(capability, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as out:
                capability_identity = os.fstat(out.fileno())
                grant={'AEVORA_RUN_ID':args.run_id, 'AEVORA_RUN_TOKEN':token,
                    'socket':str(args.socket), 'consumer_socket':'/aevora-channel/mcp.sock',
                    'transport':'aevora-mcp-uds-v1'}
                if ttl is not None:grant['expires_at']=(datetime.now(timezone.utc)+timedelta(seconds=ttl)).isoformat()
                json.dump(grant,out)
            if getattr(args,'_on_ready',None): args._on_ready()
            print(json.dumps({'status':'READY','run_id':args.run_id,'tools':sorted(broker.tools),
                'session_root':getattr(args,'_session_root',None),'capability_file':str(capability),
                'events':str(args.events),
                'consumer_access':'Scoped transport only; mount socket and stdlib proxy in isolated consumer'}),flush=True)
            while not stopped.wait(.25):
                if expires is not None and time.monotonic()>=expires:break
        print(json.dumps({'status':'REVOKED','run_id':args.run_id,'cleanup':broker.metadata}),flush=True)
        return 0
    finally:
        # Never unlink pre-existing files when O_EXCL did not succeed.
        if 'capability_identity' in locals():
            try:
                current = capability.lstat()
                if (current.st_dev,current.st_ino)==(capability_identity.st_dev,capability_identity.st_ino):capability.unlink()
            except FileNotFoundError: pass
        for sig, handler in previous.items(): signal.signal(sig,handler)
