"""Host-owned query-only Clock. Scheduling data, never task assertions or SQL.

The candidate receives exactly one Unix socket and the documented NOW protocol.
Only the trusted Python owner can advance time; a read-only mount alone is not
considered authorization. No network proxy or filesystem-reading command exists.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import stat
import struct
import tempfile
import threading
import time
from uuid import uuid4


class ClockAuthority:
    VERSION = "orderflow.request-clock/1.0"
    MAX_REQUEST = 64
    MAX_EVENTS = 10000
    MAX_CLIENTS = 16

    def __init__(self, tick: int = 100):
        self._validate_tick(tick)
        self.authority_id = str(uuid4())
        self._tick = tick
        self._lock = threading.RLock()
        self._events: list[dict] = []
        self._closed = threading.Event()
        self._directory = tempfile.TemporaryDirectory(prefix="orderflow-request-clock-")
        self.directory = Path(self._directory.name)
        self.directory.chmod(0o700)
        self.path = self.directory / "query.sock"
        self._listener = None
        self._thread = None
        self._clients: set[socket.socket] = set()
        self._handlers: set[threading.Thread] = set()
        self._slots = threading.BoundedSemaphore(self.MAX_CLIENTS)
        self._cleanup = None

    @staticmethod
    def _validate_tick(value):
        if type(value) is not int or value < 0:
            raise ValueError("Clock ticks must be nonnegative integers, excluding bool")

    @property
    def tick(self):
        with self._lock:
            return self._tick

    def _record(self, event, **details):
        with self._lock:
            if len(self._events) >= self.MAX_EVENTS:
                raise RuntimeError("Clock observation budget exhausted")
            self._events.append({"event": event, "sequence": len(self._events) + 1,
                "host_observed_ns": time.monotonic_ns(), "authority_id": self.authority_id,
                "source": "trusted_query_only_clock", **details})

    def advance(self, delta: int):
        self._validate_tick(delta)
        with self._lock:
            if self._closed.is_set():
                raise RuntimeError("Clock authority is closed")
            return self.advance_to(self._tick + delta)

    def advance_to(self, tick: int):
        self._validate_tick(tick)
        with self._lock:
            if self._closed.is_set() or tick < self._tick:
                raise ValueError("Clock cannot rewind or advance after close")
            before = self._tick
            self._record("clock.advanced", previous_tick=before, tick=tick,
                         authority="host_owner_in_process_method")
            self._tick = tick
            return tick

    def start(self):
        if self._closed.is_set():
            raise RuntimeError("A closed Clock cannot restart")
        if self._listener is not None:
            return self
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.path))
            self.path.chmod(0o600)
            listener.listen(self.MAX_CLIENTS)
            listener.settimeout(0.1)
        except BaseException:
            listener.close()
            raise
        self._listener = listener
        self._record("clock.started", tick=self.tick, protocol="NOW\\n -> JSON decimal tick")
        self._thread = threading.Thread(target=self._serve, name="orderflow-clock-accept", daemon=True)
        self._thread.start()
        return self

    def _serve(self):
        while not self._closed.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if self._closed.is_set():
                connection.close()
                break
            if not self._slots.acquire(blocking=False):
                connection.close()
                continue
            with self._lock:
                self._clients.add(connection)
            thread = threading.Thread(target=self._handle, args=(connection,),
                                      name="orderflow-clock-query", daemon=True)
            with self._lock:
                self._handlers.add(thread)
            thread.start()

    def _handle(self, connection):
        peer = None
        try:
            connection.settimeout(2)
            pid, uid, gid = struct.unpack("3i", connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            peer = {"host_pid": pid, "uid": uid, "gid": gid,
                    "pid_scope": "trusted_clock_pid_namespace; kernel_SO_PEERCRED"}
            if uid != os.getuid() or pid <= 0:
                raise PermissionError("Clock peer is not this owner's process identity")
            raw = b""
            while not raw.endswith(b"\n") and len(raw) <= self.MAX_REQUEST:
                chunk = connection.recv(self.MAX_REQUEST + 1 - len(raw))
                if not chunk:
                    break
                raw += chunk
            if raw != b"NOW\n":
                self._record("clock.request_denied", peer=peer, request_hex=raw[:self.MAX_REQUEST].hex(),
                             request_length=len(raw), reason="QUERY_ONLY_FIXED_PROTOCOL")
                connection.sendall(b'{"error":"CLOCK_QUERY_ONLY"}\n')
                return
            with self._lock:
                tick = self._tick
                self._record("clock.now", tick=tick, peer=peer)
                response = json.dumps({"tick": str(tick)}, separators=(",", ":")).encode() + b"\n"
            connection.sendall(response)
        except (OSError, ValueError, RuntimeError, PermissionError) as error:
            try:
                self._record("clock.connection_error", peer=peer, error_type=type(error).__name__)
            except RuntimeError:
                # Exhaustion closes the query channel instead of returning a
                # fabricated tick. Bounded resource refusal is not a task PASS.
                self._closed.set()
        finally:
            connection.close()
            with self._lock:
                self._clients.discard(connection)
                self._handlers.discard(threading.current_thread())
            self._slots.release()

    def evidence(self):
        with self._lock:
            return {"clock_version": self.VERSION, "authority_id": self.authority_id,
                    "tick": self._tick, "query_socket": str(self.path),
                    "events": list(self._events), "cleanup": self._cleanup,
                    "limits": {"request_bytes": self.MAX_REQUEST, "events": self.MAX_EVENTS,
                               "simultaneous_clients": self.MAX_CLIENTS, "client_seconds": 2},
                    "control_exposed_to_candidate": False,
                    "scope": "Controlled monotonic ticks; no clock-rewind/skew/power-loss claim"}

    def close(self):
        if self._cleanup is not None:
            return self.evidence()
        self._closed.set()
        if self._listener is not None:
            self._listener.close()
        # Stop the producer before snapshotting consumers. An accept that was
        # already returning may still register a client; never omit that late
        # handler from the cleanup receipt.
        if self._thread is not None:
            self._thread.join(timeout=3)
        with self._lock:
            clients, handlers = list(self._clients), list(self._handlers)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for handler in handlers:
            handler.join(timeout=3)
        alive = ([self._thread.name] if self._thread is not None and self._thread.is_alive() else [])
        alive += [thread.name for thread in handlers if thread.is_alive()]
        self._directory.cleanup()
        self._cleanup = {"complete": not alive and not self.path.exists() and not self.directory.exists(),
                         "remaining_threads": alive, "query_socket_removed": not self.path.exists()}
        return self.evidence()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()


def extend_candidate_command(command: list[str], query_socket: Path) -> list[str]:
    """Replace only the transport entry point and add two exact read-only files.

    Keep all original namespace/capability/resource arguments and mount parents
    out of scope. No hidden suite, Oracle or reference is mounted.
    """
    query_socket = Path(query_socket).absolute()
    info = query_socket.lstat()
    parent = query_socket.parent.lstat()
    if (query_socket.is_symlink() or query_socket.resolve(strict=True) != query_socket
            or not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid() or parent.st_mode & 0o077):
        raise ValueError("Clock requires this owner's ordinary private query socket")
    command = list(command)
    matches = [index for index in range(len(command) - 2)
               if command[index] == "--ro-bind" and command[index + 2] == "/worker.py"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one existing generic worker bind")
    index = matches[0]
    generic_worker = Path(__file__).with_name("worker.py").resolve(strict=True)
    if Path(command[index + 1]).resolve(strict=True) != generic_worker:
        raise ValueError("Unexpected original generic worker source")
    command[index + 1] = str(Path(__file__).with_name("dv02_worker.py").resolve(strict=True))
    addition = ["--ro-bind", str(generic_worker), "/worker_base.py",
                "--ro-bind", str(query_socket), "/clock-query.sock"]
    command = command[:index] + addition + command[index:]
    clears = [index for index, argument in enumerate(command) if argument == "--clearenv"]
    if len(clears) != 1:
        raise ValueError("Expected exactly one existing environment reset")
    index = clears[0] + 1
    return command[:index] + ["--setenv", "ORDERFLOW_CLOCK_QUERY", "/clock-query.sock"] + command[index:]
