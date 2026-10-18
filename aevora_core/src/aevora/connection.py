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


def serve(args, repo):
    from .cli import read_json
    context = normalize_context(read_json(args.context))
    capability = Path(args.capability_file)
    if capability.parent.is_symlink() or capability.parent.stat().st_mode & 0o077:
        raise ValueError('Capability parent must be an owned private directory')
    if capability.parent.stat().st_uid != os.getuid(): raise ValueError('Capability directory owner mismatch')
    # Confirm real availability before granting a channel. Empty graph is valid.
    repo.state_fingerprint()
    stopped = threading.Event()
    previous = {}
    def stop(*_): stopped.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, stop)
    token = secrets.token_urlsafe(32)
    ttl=getattr(args,'capability_ttl',None)
    if ttl is not None and (type(ttl) is not int or not 1<=ttl<=86400):
        raise ValueError('Explicit capability TTL must be 1..86400 seconds')
    expires=time.monotonic()+ttl if ttl is not None else None
    try:
        with MCPBroker(run_id=args.run_id, public_context=context, socket_path=Path(args.socket), run_token=token,
                event_path=Path(args.events), enable_proposals=args.enable_proposals) as broker:
            fd = os.open(capability, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as out:
                grant={'AEVORA_RUN_ID':args.run_id, 'AEVORA_RUN_TOKEN':token,
                    'socket':str(args.socket), 'consumer_socket':'/aevora-channel/mcp.sock',
                    'transport':'aevora-mcp-uds-v1'}
                if ttl is not None:grant['expires_at']=(datetime.now(timezone.utc)+timedelta(seconds=ttl)).isoformat()
                json.dump(grant,out)
            print(json.dumps({'status':'READY','run_id':args.run_id,'tools':sorted(broker.tools),
                'consumer_access':'Scoped transport only; mount socket and stdlib proxy in isolated consumer'}),flush=True)
            while not stopped.wait(.25):
                if expires is not None and time.monotonic()>=expires:break
        print(json.dumps({'status':'REVOKED','run_id':args.run_id,'cleanup':broker.metadata}),flush=True)
        return 0
    finally:
        # Never unlink pre-existing files when O_EXCL did not succeed.
        if 'fd' in locals(): capability.unlink(missing_ok=True)
        for sig, handler in previous.items(): signal.signal(sig,handler)
