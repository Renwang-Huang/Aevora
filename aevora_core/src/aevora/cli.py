"""Independent public Core entry point; administrative calls are HOST ONLY.

Never install/run this administrative executable in an Agent namespace with
database credentials. The public transport uses the existing revocable broker,
not direct DB access. No OrderFlow imports except explicit source-orderflow.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import signal
import sys
import threading
from .candidate import CandidateLifecycle, ReviewGrant
from .graph_repository import GraphRepository
from .mcp_server import ExperienceService


def read_json(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
        raise ValueError('Bounded ordinary JSON file required')
    return json.loads(p.read_text())


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest='operation', required=True)
    for name in ('init', 'health'): s.add_parser(name)
    q = s.add_parser('query'); q.add_argument('--run-id', required=True); q.add_argument('--context', required=True)
    q = s.add_parser('inspect'); q.add_argument('--candidate', required=True)
    q = s.add_parser('review')
    q.add_argument('--candidate', required=True); q.add_argument('--state', required=True)
    q.add_argument('--expected-head', required=True); q.add_argument('--event-key', required=True)
    q.add_argument('--reason', required=True); q.add_argument('--principal', required=True)
    q.add_argument('--metadata'); q.add_argument('--grant-seconds', type=int, default=300)
    q = s.add_parser('source-orderflow'); q.add_argument('--candidate', required=True); q.add_argument('--anchor', required=True)
    q.add_argument('--report', default='evaluation_report.json')
    q = s.add_parser('serve')
    q.add_argument('--run-id', required=True); q.add_argument('--context', required=True)
    q.add_argument('--socket', required=True); q.add_argument('--capability-file', required=True)
    q.add_argument('--events', required=True); q.add_argument('--enable-proposals', action='store_true')
    q.add_argument('--capability-ttl', type=int, default=None,
                   help='Optional explicit local grant expiry (1..86400 seconds); default follows owner lifetime')
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    repo = GraphRepository.from_environment()
    try:
        life = CandidateLifecycle(repo)
        if a.operation == 'init': value = life.initialize()
        elif a.operation == 'health': value = {'status': 'AVAILABLE', 'graph_state': repo.state_fingerprint()}
        elif a.operation == 'query':
            value = ExperienceService(run_id=a.run_id, public_context=read_json(a.context), repository=repo).resolve_experience({})
        elif a.operation == 'inspect': value = life.inspect(a.candidate)
        elif a.operation == 'source-orderflow':
            from .orderflow_outcome_bridge import TrustAnchor
            from .admission import verify_orderflow_candidate
            value = verify_orderflow_candidate(repo, a.candidate, TrustAnchor(**read_json(a.anchor)), a.report)
        elif a.operation == 'review':
            if not 1 <= a.grant_seconds <= 3600: raise ValueError('Grant is bounded to one hour')
            grant = ReviewGrant(a.principal, (datetime.now(timezone.utc)+timedelta(seconds=a.grant_seconds)).isoformat())
            kwargs = dict(expected_head_sha256=a.expected_head, event_key=a.event_key, reason=a.reason, grant=grant)
            value = (life.publish(a.candidate, **kwargs) if a.state == 'PUBLISHED'
                     else life.transition(a.candidate, a.state, metadata=read_json(a.metadata) if a.metadata else None, **kwargs))
        else:
            from .connection import serve
            return serve(a, repo)
        print(json.dumps(value, sort_keys=True, allow_nan=False)); return 0
    finally: repo.close()


def entrypoint(argv=None):
    """Consistent sanitized process boundary for console-script and -m usage.

    main() keeps its Python-call exception contract. Public executables never
    print database/credential exception details or an unbounded traceback.
    """
    try:return main(argv)
    except Exception as e:
        print(json.dumps({'status': 'ERROR', 'error_type': type(e).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':raise SystemExit(entrypoint())
