"""Maintainer-only D-v02 fixture construction and exact strategy diffs.

Public templates are copied into this challenge alone. The old app baseline,
Episode D/v01 truth and historical outcomes are never edited by the builder.
"""
import difflib
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = Path(__file__).with_name("dv02_public")
FIXTURE_VERSION = "1.0.0"
VARIANT = "v02"
IMPLEMENTATIONS = ("buggy", "reference", "flock", "inventory_only", "local_lock", "blind_cleanup")

_SERVICE = '''"""OrderFlow business facade, including the public two-stage request API."""
from app.legacy_service import OrderFlow as LegacyOrderFlow
from app.requests import RequestAPI


class OrderFlow(RequestAPI, LegacyOrderFlow):
    pass
'''

_WRITER_GUARD = '''

import contextlib
import functools
import threading

_service_writer_lock = threading.RLock()

def _coordinate_writer(method):
    @functools.wraps(method)
    def coordinated(self, *args, **kwargs):
        with _service_writer_lock:
            with _shared_writer_guard(self):
                return method(self, *args, **kwargs)
    return coordinated

for _method in ("initialize", "create_order", "reserve_inventory", "cancel_order",
                "release_inventory", "claim_request", "renew_request",
                "complete_request", "cancel_request"):
    setattr(OrderFlow, _method, _coordinate_writer(getattr(OrderFlow, _method)))
'''

_LOCAL_GUARD = '''
def _shared_writer_guard(flow):
    return contextlib.nullcontext()
'''

_FLOCK_GUARD = '''
import fcntl

@contextlib.contextmanager
def _shared_writer_guard(flow):
    flow.persistence.db_path.parent.mkdir(parents=True, exist_ok=True)
    # Never unlink this file: all workers coordinate on the same stable inode.
    with open(str(flow.persistence.db_path) + ".requests.lock", "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
'''

_DEFERRED = '''

from contextlib import contextmanager

@contextmanager
def _shared_request_transaction(self):
    # The enclosing cooperative file lock supplies writer exclusion. SQLite
    # still couples the operation's durable records with an atomic transaction.
    with self.persistence.connection() as connection:
        connection.execute("BEGIN")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

RequestAPI._request_transaction = _shared_request_transaction
'''

_BLIND_CLEANUP = '''

_complete_with_cleanup = OrderFlow.complete_request

def _complete_and_cleanup(self, handle):
    try:
        return _complete_with_cleanup(self, handle)
    finally:
        if isinstance(handle, dict) and isinstance(handle.get("request_id"), str):
            with self.persistence.transaction() as connection:
                connection.execute("UPDATE requests SET current_token=NULL,deadline=NULL "
                                   "WHERE request_id=? AND status='PENDING'", (handle["request_id"],))

OrderFlow.complete_request = _complete_and_cleanup
'''


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("D-v02 source boundary changed; review the fixture version")
    return source.replace(old, new, 1)


def _reference(source):
    source = _once(source,
        '        return claim is not None and claim["request_id"] == request["request_id"]\n',
        '        return (claim is not None and claim["request_id"] == request["request_id"]\n'
        '                and request["status"] == "PENDING"\n'
        '                and request["current_token"] == claim["token"]\n'
        '                and request["deadline"] is not None and tick < int(request["deadline"]))\n')
    source = _once(source,
        '            if request["status"] == "COMPLETED":\n'
        '                return json.loads(request["receipt_json"])\n',
        '            if request["status"] != "PENDING":\n'
        '                return json.loads(request["receipt_json"])\n')
    source = _once(source,
        '                connection.execute("UPDATE requests SET current_token=NULL,deadline=NULL WHERE request_id=?",\n'
        '                                   (request_id,))\n',
        '                connection.execute("UPDATE requests SET current_token=NULL,deadline=NULL "\n'
        '                                   "WHERE request_id=? AND current_token=? AND status=\'PENDING\'",\n'
        '                                   (request_id, token))\n')
    return source


def implementation_sources(implementation="buggy", variant=VARIANT):
    if variant != VARIANT or implementation not in IMPLEMENTATIONS:
        raise ValueError("Unsupported D-v02 variant or implementation")
    sources = {path.name: path.read_text() for path in sorted(PUBLIC.glob("*.py"))}
    sources["legacy_service.py"] = (ROOT / "app/service.py").read_text()
    sources["service.py"] = _SERVICE
    if implementation in ("reference", "flock", "blind_cleanup"):
        sources["requests.py"] = _reference(sources["requests.py"])
    if implementation == "flock":
        source = sources["requests.py"].replace("self.persistence.transaction()", "self._request_transaction()")
        source += _DEFERRED
        sources["requests.py"] = source
        # Define the guard before applying the decoration.
        split = _WRITER_GUARD.index("for _method")
        sources["service.py"] += _WRITER_GUARD[:split] + _FLOCK_GUARD + _WRITER_GUARD[split:]
    elif implementation == "local_lock":
        split = _WRITER_GUARD.index("for _method")
        sources["service.py"] += _WRITER_GUARD[:split] + _LOCAL_GUARD + _WRITER_GUARD[split:]
    elif implementation == "blind_cleanup":
        sources["service.py"] += _BLIND_CLEANUP
    # inventory_only is explicitly the same capacity-safe defect artifact,
    # rather than a fabricated different implementation or repair.
    return sources


def build_episode_d_v02(destination, variant=VARIANT, *, implementation="buggy"):
    sources = implementation_sources(implementation, variant)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "app").exists():
        raise ValueError("D-v02 fixture requires a new app tree")
    shutil.copytree(ROOT / "app", destination / "app", ignore=shutil.ignore_patterns("__pycache__"))
    for name, source in sources.items():
        (destination / "app" / name).write_text(source, encoding="utf-8")
    return destination


def episode_d_v02_patch(implementation="reference", variant=VARIANT):
    if implementation not in IMPLEMENTATIONS or implementation in ("buggy", "inventory_only"):
        raise ValueError("This implementation is the unchanged defect baseline")
    old, new = implementation_sources("buggy", variant), implementation_sources(implementation, variant)
    parts = []
    for name in sorted(old.keys() | new.keys()):
        parts.extend(difflib.unified_diff(old.get(name, "").splitlines(keepends=True),
                                         new.get(name, "").splitlines(keepends=True),
                                         fromfile="a/app/" + name, tofile="b/app/" + name))
    return "".join(parts)
