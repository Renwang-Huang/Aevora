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
from .candidate import CandidateLifecycle, ReviewGrant, lifecycle_next_steps
from .graph_repository import GraphRepository
from .mcp_server import ExperienceService
from .host_config import configure, prepare_environment
from .startup import StartupError


class SourceProjectRejected(ValueError):
    """Only fixed adapter validation messages may cross this sanitized boundary."""


def read_json(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
        raise ValueError('Bounded ordinary JSON file required')
    return json.loads(p.read_text())


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', help='Protected Host profile; defaults to ~/.config/aevora/host.json when no DB environment is set')
    s = p.add_subparsers(dest='operation', required=True)
    q = s.add_parser('configure', help='Save Host settings for subsequent terminals; stores secret file references only')
    q.add_argument('--output'); q.add_argument('--host', default='127.0.0.1'); q.add_argument('--port', type=int, required=True)
    q.add_argument('--graph', required=True); q.add_argument('--password-file', required=True)
    q.add_argument('--session-root', default=str(Path.home()/'.local/state/aevora/local'))
    q.add_argument('--console-port', type=int, default=17805); q.add_argument('--context')
    q = s.add_parser('mcp-config', help='Print a stable connector stanza for the configured session root')
    q.add_argument('--python', default=sys.executable); q.add_argument('--session-root')
    for name in ('init', 'health'): s.add_parser(name)
    q = s.add_parser('query'); q.add_argument('--run-id', required=True); q.add_argument('--context', required=True)
    q = s.add_parser('inspect'); q.add_argument('--candidate', required=True)
    q = s.add_parser('review')
    q.add_argument('--candidate', required=True); q.add_argument('--state', required=True)
    q.add_argument('--expected-head', required=True); q.add_argument('--event-key', required=True)
    q.add_argument('--reason', required=True); q.add_argument('--principal', required=True)
    q.add_argument('--metadata'); q.add_argument('--grant-seconds', type=int, default=300)
    q.add_argument('--source', help='Verified source ID for bounded admission')
    q.add_argument('--scope', help='Host-reviewed factual scope JSON for bounded admission')
    q = s.add_parser('source-project', help='Verify Host-authorized independent project artifacts')
    q.add_argument('--candidate', required=True); q.add_argument('--policy', required=True)
    q.add_argument('--evidence-root', required=True)
    q.add_argument('--receipt-sha256', required=True,
        help='Pin authorized through the independent verifier channel; not an Agent self-report checksum')
    q = s.add_parser('source-orderflow'); q.add_argument('--candidate', required=True); q.add_argument('--anchor', required=True)
    q.add_argument('--report', default='evaluation_report.json')
    q = s.add_parser('serve')
    q.add_argument('--run-id'); q.add_argument('--context')
    q.add_argument('--session-root', help='Create a fresh session per launch; connector can follow this stable root')
    q.add_argument('--socket'); q.add_argument('--capability-file')
    q.add_argument('--events'); q.add_argument('--enable-proposals', action='store_true')
    q.add_argument('--capability-ttl', type=int, default=None,
                   help='Optional explicit local grant expiry (1..86400 seconds); default follows owner lifetime')
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    if a.operation == 'configure':
        print(json.dumps(configure(a), sort_keys=True)); return 0
    profile = prepare_environment(a.config)
    if a.operation == 'mcp-config':
        root = a.session_root or (profile['session']['root'] if profile else None)
        if not root: raise StartupError('SESSION_ROOT_REQUIRED', 'No session root is configured.', 'Run aevora configure, or provide --session-root PATH.')
        from .mcp_config import stanza
        print(stanza(a.python,session_root=root),end=''); return 0
    if a.operation == 'serve':
        explicit = [a.socket, a.capability_file, a.events]
        if any(explicit) and (not all(explicit) or a.session_root or not a.run_id or not a.context):
            raise StartupError('SESSION_ARGUMENTS_INVALID', 'Explicit session paths must be provided together with Run and context.', 'Use managed aevora serve with a profile/--session-root, or supply all legacy path arguments without --session-root.')
        if not any(explicit):
            a.session_root = a.session_root or (profile['session']['root'] if profile else None)
            if not a.session_root:
                raise StartupError('SESSION_ROOT_REQUIRED', 'No managed session root is configured.', 'Run aevora configure, or provide --session-root with a short private absolute path.')
        a._public_context = profile['session']['public_context'] if profile else {}
    repo = GraphRepository.from_environment()
    try:
        life = CandidateLifecycle(repo)
        if a.operation == 'init': value = life.initialize()
        elif a.operation == 'health': value = {'status': 'AVAILABLE', 'graph_state': repo.state_fingerprint()}
        elif a.operation == 'query':
            value = ExperienceService(run_id=a.run_id, public_context=read_json(a.context), repository=repo).resolve_experience({})
        elif a.operation == 'inspect':
            value = life.inspect(a.candidate)
            value['next_steps'] = lifecycle_next_steps(value['head']['state'])
        elif a.operation == 'source-project':
            from .project_source import load_policy, verify_project_candidate
            from .source_evidence import OutcomeVerificationError
            try:
                value = verify_project_candidate(repo, a.candidate, policy=load_policy(a.policy),
                    evidence_root=a.evidence_root, receipt_sha256=a.receipt_sha256)
            except OutcomeVerificationError as error:
                raise SourceProjectRejected(str(error)) from None
        elif a.operation == 'source-orderflow':
            from .orderflow_outcome_bridge import TrustAnchor
            from .admission import verify_orderflow_candidate
            value = verify_orderflow_candidate(repo, a.candidate, TrustAnchor(**read_json(a.anchor)), a.report)
        elif a.operation == 'review':
            if a.source or a.scope:
                if a.metadata or a.state!='ADMITTED_BOUNDED' or not (a.source and a.scope):
                    raise ValueError('Use source and scope together only for bounded admission')
                metadata = {'source_id':a.source, 'scope':read_json(a.scope), 'strength':'BOUNDED_SUPPORT_NOT_CAUSAL'}
            else: metadata = read_json(a.metadata) if a.metadata else None
            if not 1 <= a.grant_seconds <= 3600: raise ValueError('Grant is bounded to one hour')
            grant = ReviewGrant(a.principal, (datetime.now(timezone.utc)+timedelta(seconds=a.grant_seconds)).isoformat())
            kwargs = dict(expected_head_sha256=a.expected_head, event_key=a.event_key, reason=a.reason, grant=grant)
            value = (life.publish(a.candidate, **kwargs) if a.state == 'PUBLISHED'
                     else life.transition(a.candidate, a.state, metadata=metadata, **kwargs))
        else:
            from .connection import serve
            if a.session_root:
                from .local_session import SessionLease
                with SessionLease(a.session_root, a) as managed: return serve(managed, repo)
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
        if isinstance(e,StartupError):
            print(json.dumps(e.public(), sort_keys=True), file=sys.stderr); return 2
        value={'status': 'ERROR', 'error_type': type(e).__name__}
        if isinstance(e,SourceProjectRejected):
            value.update(reason=str(e),next_step='Check the protected Host policy, independently authorized pin and complete verifier artifacts; keep the candidate pending.')
        print(json.dumps(value), file=sys.stderr)
        return 2


if __name__ == '__main__':raise SystemExit(entrypoint())
