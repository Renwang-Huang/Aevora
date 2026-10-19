"""Host-only bounded scheduling channel; it contains no business oracle.

Each endpoint accepts one trusted generic worker before candidate import. Its
identity comes from kernel SO_PEERCRED, not a candidate-supplied PID. No command
can read a host file, execute SQL, proxy network traffic or access model auth.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import select
import socket
import struct
import tempfile
import threading
import time


CONTROL_VERSION = 1
STOP_LABELS = frozenset({"before_commit", "transaction_committed", "before_response"})
MAX_MESSAGE_BYTES = 16384
MAX_EVENTS_PER_WORKER = 5000


def process_identity(pid: int) -> dict:
    """Record a PID in the trusted supervisor's namespace and stable start time."""
    root = Path("/proc") / str(pid)
    raw = (root / "stat").read_text()
    fields = raw[raw.rindex(")") + 2:].split()
    status = (root / "status").read_text().splitlines()
    nspid = next((line.split()[1:] for line in status if line.startswith("NSpid:")), [])
    namespaces = {}
    for name in ("pid", "mnt", "net", "user"):
        try:
            namespaces[name] = os.readlink(root / "ns" / name)
        except OSError:
            namespaces[name] = "UNAVAILABLE"
    return {"host_pid": pid, "pid_scope": "trusted_supervisor_pid_namespace",
            "start_ticks": int(fields[19]), "parent_pid": int(fields[1]),
            "nspid": [int(value) for value in nspid], "namespaces": namespaces}


class BoundedGate:
    """One optional first-wave checkpoint; timeout releases it permanently."""
    def __init__(self, label: str, parties: int, timeout_seconds: float = 0.3):
        if not isinstance(label, str) or not label or len(label) > 128:
            raise ValueError("Checkpoint label must be a bounded nonempty string")
        if type(parties) is not int or not 1 <= parties <= 4:
            raise ValueError("Checkpoint parties must be between one and four")
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 0.3:
            raise ValueError("Process checkpoint timeout must be in (0, 0.3]")
        self.label, self.parties, self.timeout_seconds = label, parties, float(timeout_seconds)
        self._lock = threading.Lock()
        self._release = threading.Event()
        self._arrivals = {}
        self._released_by = None

    def arrive(self, worker_index: int, label: str) -> None:
        if label != self.label:
            return
        with self._lock:
            if worker_index in self._arrivals:
                return
            self._arrivals[worker_index] = time.monotonic_ns()
            if len(self._arrivals) >= self.parties and not self._release.is_set():
                self._released_by = "all_arrived"
                self._release.set()
        if not self._release.wait(self.timeout_seconds):
            with self._lock:
                if not self._release.is_set():
                    self._released_by = "timeout"
                    self._release.set()

    def release(self):
        with self._lock:
            if not self._release.is_set():
                self._released_by = "host_release"
                self._release.set()

    def observation(self) -> dict:
        with self._lock:
            return {"label": self.label, "parties": self.parties,
                    "timeout_seconds": self.timeout_seconds,
                    "arrival_worker_indices": sorted(self._arrivals),
                    "arrival_host_ns": dict(self._arrivals), "arrivals": len(self._arrivals),
                    "released_by": self._released_by or "unused"}


class StopObservation:
    def __init__(self, label):
        if label not in STOP_LABELS:
            raise ValueError("Unknown generic worker stop observation")
        self.label = label
        self.arrived = threading.Event()
        self.release = threading.Event()
        self.event = None
        self.released_by = None


class WorkerControl:
    """A small fixed set of private endpoints, one per independent Worker."""
    def __init__(self, worker_count: int, *, on_event=None):
        if worker_count not in (2, 4) or type(worker_count) is not int:
            raise ValueError("Control supports exactly two or four workers")
        self.worker_count = worker_count
        self._directory = tempfile.TemporaryDirectory(prefix="of-worker-control-")
        self.directory = Path(self._directory.name)
        os.chmod(self.directory, 0o700)
        self.paths = []
        self._listeners, self._threads = [], []
        self._connections = {}
        self._identities, self._pidfds = {}, {}
        self._events = {index: [] for index in range(worker_count)}
        self._ready = {index: threading.Event() for index in range(worker_count)}
        self._launch_authorized = {index: False for index in range(worker_count)}
        self._expected_disconnect = set()
        self.on_event = on_event
        self._stops = {}
        self._gate = None
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self.errors = []
        for index in range(worker_count):
            path = self.directory / f"worker-{index}.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            os.chmod(path, 0o600)
            listener.listen(1)
            listener.settimeout(0.2)
            self.paths.append(path)
            self._listeners.append(listener)
            thread = threading.Thread(target=self._serve, args=(index, listener),
                                      name=f"orderflow-worker-control-{index}", daemon=True)
            self._threads.append(thread)
            thread.start()

    def _serve(self, index, listener):
        while not self._closed.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                try:
                    pid, uid, gid = struct.unpack("3i", connection.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
                    if uid != os.getuid() or pid <= 1:
                        raise ValueError("Worker peer credentials are outside the trusted launch")
                    identity = process_identity(pid)
                    identity.update(peer_uid=uid, peer_gid=gid, worker_index=index)
                    pidfd = os.pidfd_open(pid)
                    with self._lock:
                        if index in self._connections or not self._launch_authorized[index]:
                            os.close(pidfd)
                            raise ValueError("Worker control connection requires an explicitly authorized new generation")
                        self._launch_authorized[index] = False
                        old_fd = self._pidfds.pop(index, None)
                        if old_fd is not None:
                            os.close(old_fd)
                        self._connections[index] = connection
                        self._identities[index] = identity
                        self._pidfds[index] = pidfd
                    connection.settimeout(45)
                    stream = connection.makefile("rb")
                    try:
                        first = True
                        while not self._closed.is_set():
                            raw = stream.readline(MAX_MESSAGE_BYTES + 1)
                            if not raw:
                                break
                            if len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                                raise ValueError("Worker control message exceeds its bound")
                            message = json.loads(raw)
                            if not isinstance(message, dict) or set(message) != {"event", "metadata"}:
                                raise ValueError("Invalid control message envelope")
                            kind, metadata = message["event"], message["metadata"]
                            if not isinstance(metadata, dict):
                                raise ValueError("Control metadata must be an object")
                            if first:
                                if kind != "hello" or metadata.get("protocol_version") != CONTROL_VERSION:
                                    raise ValueError("Worker control handshake failed")
                                first = False
                                self._ready[index].set()
                            elif kind not in STOP_LABELS | {"checkpoint"}:
                                raise ValueError("Unknown control event; no host service is exposed")
                            event = {"event": kind, "worker_index": index,
                                     "host_pid": pid, "host_observed_ns": time.monotonic_ns(),
                                     "metadata": metadata}
                            with self._lock:
                                if len(self._events[index]) >= MAX_EVENTS_PER_WORKER:
                                    raise ValueError("Worker control event budget exhausted")
                                self._events[index].append(event)
                                gate = self._gate
                                stop = self._stops.get(index)
                            if self.on_event is not None:
                                self.on_event(event)
                            if kind == "checkpoint" and gate is not None:
                                gate.arrive(index, metadata.get("label"))
                            if stop is not None and kind == stop.label and not stop.arrived.is_set():
                                stop.event = event
                                stop.arrived.set()
                                if not stop.release.wait(5):
                                    stop.released_by = "bounded_timeout"
                                    stop.release.set()
                            connection.sendall(b'{"command":"continue"}\n')
                    finally:
                        stream.close()
                except (OSError, ValueError, UnicodeError) as error:
                    if not self._closed.is_set():
                        with self._lock:
                            if index not in self._expected_disconnect or isinstance(error, (ValueError, UnicodeError)):
                                self.errors.append({"worker_index": index, "kind": type(error).__name__,
                                                    "message": str(error)[:500]})
                finally:
                    with self._lock:
                        self._connections.pop(index, None)

    def prepare_restart(self, index):
        self.disarm(index)
        self._ready[index].clear()
        # Wait for an old killed worker's connection handler to release ownership.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with self._lock:
                if index not in self._connections:
                    self._launch_authorized[index] = True
                    self._expected_disconnect.discard(index)
                    return
            time.sleep(0.01)
        raise RuntimeError("Previous worker control connection has not closed")

    def wait_ready(self, index, timeout=5):
        if not self._ready[index].wait(timeout):
            raise RuntimeError("Worker did not establish its pre-import control identity")
        with self._lock:
            return dict(self._identities[index])

    def set_gate(self, checkpoint, parties):
        if checkpoint is None:
            self._gate = None
            return
        if not isinstance(checkpoint, dict) or set(checkpoint) - {"label", "timeout_seconds"}:
            raise ValueError("Invalid generic process checkpoint")
        self._gate = BoundedGate(checkpoint.get("label"), parties, checkpoint.get("timeout_seconds", 0.3))

    def gate_observation(self):
        return self._gate.observation() if self._gate else None

    def arm_stop(self, index, label):
        self.disarm(index)
        with self._lock:
            self._stops[index] = StopObservation(label)

    def wait_stop(self, index, timeout=5):
        with self._lock:
            stop = self._stops.get(index)
        if stop is None:
            raise ValueError("Worker has no armed stop")
        if not stop.arrived.wait(timeout):
            return {"availability": "UNAVAILABLE", "label": stop.label,
                    "reason": "Candidate did not reach this optional observation in the interval"}
        return {"availability": "AVAILABLE", "label": stop.label, "event": dict(stop.event)}

    def release(self, index):
        with self._lock:
            stop = self._stops.get(index)
        if stop is not None:
            stop.released_by = "host_release"
            stop.release.set()

    def disarm(self, index):
        with self._lock:
            stop = self._stops.pop(index, None)
        if stop is not None:
            stop.released_by = "host_disarm"
            stop.release.set()

    def kill(self, index):
        with self._lock:
            fd = self._pidfds.get(index)
            identity = dict(self._identities.get(index, {}))
        if fd is None:
            raise RuntimeError("No kernel-identified worker to kill")
        started = time.monotonic_ns()
        with self._lock:
            self._expected_disconnect.add(index)
        signal.pidfd_send_signal(fd, signal.SIGKILL)
        self.release(index)
        exited, _, _ = select.select([fd], [], [], 2)
        return {"signal": "SIGKILL", "identity": identity,
                "host_start_ns": started, "host_end_ns": time.monotonic_ns(),
                "mechanism": "pidfd_send_signal", "worker_pidfd_exited": bool(exited)}

    def observation(self):
        with self._lock:
            return {"protocol_version": CONTROL_VERSION,
                    "identities": {index: dict(row) for index, row in self._identities.items()},
                    "events": {index: list(rows) for index, rows in self._events.items()},
                    "errors": list(self.errors), "checkpoint": self.gate_observation()}

    def close(self):
        self._closed.set()
        if self._gate is not None:
            self._gate.release()
        for index in range(self.worker_count):
            self.release(index)
        with self._lock:
            connections = list(self._connections.values())
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for listener in self._listeners:
            listener.close()
        for thread in self._threads:
            thread.join(timeout=2)
        for fd in self._pidfds.values():
            os.close(fd)
        self._pidfds.clear()
        self._directory.cleanup()
