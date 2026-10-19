"""Trusted, per-run status and cancellation; never mounted into Participant.

Activity is observed, not a heartbeat fabricated for Codex. A snapshot is partial
and cannot establish hidden-test correctness or replace final native evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import threading
import time
from uuid import UUID

from integrations.codex_trace import redact


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_read(path: Path, limit=2_000_000):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > limit:
            raise ValueError("Unsafe runtime control file")
        return os.read(descriptor, limit + 1)
    finally:
        os.close(descriptor)


def _directory(archive):
    path = Path(archive).absolute()
    if path.is_symlink() or path.resolve(strict=True) != path or not path.is_dir():
        raise ValueError("Run archive must be an ordinary trusted directory")
    if path.stat().st_uid != os.getuid():
        raise ValueError("Run archive belongs to another owner")
    return path


def _atomic(path, value):
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(redact(value), output, sort_keys=True, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def status_run(archive: Path) -> dict:
    archive = _directory(archive)
    control = json.loads(_safe_read(archive / "runtime_control.json"))
    snapshot = json.loads(_safe_read(archive / "runtime_status.json"))
    try:
        canonical = str(UUID(archive.name)) == archive.name
    except ValueError:
        canonical = False
    if not canonical or control.get("run_id") != archive.name or control.get("run_id") != snapshot.get("run_id") or control.get("control_id") != snapshot.get("control_id"):
        raise ValueError("Runtime status does not belong to this control identity")
    return snapshot


def snapshot_run(archive: Path) -> dict:
    """Read already-observed state; never modify official/raw evidence."""
    return status_run(archive)


def cancel_run(archive: Path, reason: str = "operator request") -> dict:
    archive = _directory(archive)
    snapshot = status_run(archive)
    if snapshot.get("status") != "RUNNING":
        raise ValueError("Only a currently running session can be cancelled")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
        raise ValueError("Cancellation reason must be a bounded nonempty string")
    request = {"run_id": snapshot["run_id"], "control_id": snapshot["control_id"],
               "requested_at": _now(), "reason": redact(reason), "source": "trusted_operator",
               "classification": "CANCELLED_BY_OPERATOR"}
    # Publish complete bytes atomically. Opening the final path before dump()
    # let the running controller observe empty/partial JSON and misclassify a
    # legitimate cancellation as a startup ERROR. The exclusive publication
    # lock preserves duplicate-request rejection; it grants no Participant
    # authority and no signal is sent to a namespace-ambiguous PID.
    publication = archive / ".operator_cancel.publish"
    publication.mkdir(mode=0o700)
    try:
        target = archive / "operator_cancel.json"
        if target.exists() or target.is_symlink():
            raise FileExistsError("Cancellation has already been requested")
        _atomic(target, request)
    finally:
        publication.rmdir()
    return {"status": "CANCEL_REQUESTED", **request}


class RuntimeControl:
    def __init__(self, archive: Path, run_id: str, *, completion_policy: str, agent_mode: str):
        self.archive = _directory(archive)
        if run_id != self.archive.name or str(UUID(run_id)) != run_id:
            raise ValueError("Runtime control requires this archive's canonical Run ID")
        self.control = {"schema_version": "1.0.0", "run_id": run_id,
                        "control_id": secrets.token_hex(16), "controller_pid": os.getpid(),
                        "controller_pid_namespace": os.readlink("/proc/self/ns/pid"),
                        "completion_policy": completion_policy, "agent_mode": agent_mode,
                        "started_at": _now()}
        self.activity_path = archive / "runtime_activity.jsonl"
        self._output = self.activity_path.open("x")
        self._lock = threading.Lock()
        self._cancel = None
        self._handlers = {}
        self._raw_offset = 0
        self._raw_pending = b""
        self._raw_line = 0
        self._recent = None
        self._children = {}
        self._tools = {}
        self._usage = {"availability": "UNAVAILABLE"}
        self._last_progress = time.monotonic()
        self.baseline_tree_sha256 = None
        self._first_patch_observed = None
        self._snapshot = {**self.control, "status": "RUNNING", "evidence_status": "PARTIAL_SNAPSHOT"}
        _atomic(archive / "runtime_control.json", self.control)
        _atomic(archive / "runtime_status.json", self._snapshot)

    def install_signals(self):
        if threading.current_thread() is not threading.main_thread():
            return
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._handlers[signum] = signal.getsignal(signum)
            def handler(received, frame):
                self._cancel = {"source": "trusted_controller_signal", "signal": received,
                                "requested_at": _now(), "reason": signal.Signals(received).name,
                                "classification": "CANCELLED_BY_OPERATOR" if received == signal.SIGINT else "COLLECTOR_INTERRUPTED"}
            signal.signal(signum, handler)

    def event(self, kind, detail):
        event = {"run_id": self.control["run_id"], "timestamp": _now(),
                 "source": "trusted_runtime_observer", "event_type": kind, "detail": redact(detail)}
        with self._lock:
            self._output.write(json.dumps(event, sort_keys=True) + "\n")
            self._output.flush()
        self._recent = event
        return event

    def cancellation(self):
        path = self.archive / "operator_cancel.json"
        if self._cancel is None and (path.exists() or path.is_symlink()):
            request = json.loads(_safe_read(path, 8192))
            if request.get("run_id") != self.control["run_id"] or request.get("control_id") != self.control["control_id"]:
                raise ValueError("Cancellation request belongs to another run")
            if request.get("classification") != "CANCELLED_BY_OPERATOR":
                raise ValueError("Invalid cancellation classification")
            self._cancel = request
        return self._cancel

    def observe_exec(self, path: Path, *, secret_values=()):
        if not path.exists():
            return
        with path.open("rb") as raw:
            raw.seek(self._raw_offset)
            data = raw.read(2_000_000)
        self._raw_offset += len(data)
        self._raw_pending += data
        lines = self._raw_pending.split(b"\n")
        self._raw_pending = lines.pop()
        # A malformed gigantic line is not a trusted progress signal.
        if len(self._raw_pending) > 2_000_000:
            self._raw_pending = b""
        for body in lines:
            self._raw_line += 1
            line = body + b"\n"
            try:
                value = json.loads(body)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(value, dict):
                continue
            cleaned = redact(value, secret_values=secret_values)
            if cleaned != value:
                line = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
            value = cleaned
            item = value.get("item", {})
            item = item if isinstance(item, dict) else {}
            kind = value.get("type")
            observation = {"official_type": kind, "item_type": item.get("type"),
                           "source_reference": {"file": "codex_events.jsonl", "line": self._raw_line,
                                                "line_sha256": sha256(line).hexdigest(), "availability": "PENDING_FINAL_ARCHIVE"}}
            if kind in ("item.started", "item.updated", "item.completed"):
                item_id = item.get("id")
                if item.get("type") == "command_execution" and isinstance(item_id, str):
                    self._tools[item_id] = "RUNNING" if kind != "item.completed" else "COMPLETED"
                if item.get("type") == "collab_tool_call":
                    observation["tool"] = item.get("tool")
                    states = item.get("agents_states", {})
                    if isinstance(states, dict):
                        for agent, state in states.items():
                            self._children[agent] = state
                    if item.get("tool") == "wait" and kind != "item.completed":
                        self._tools[str(item_id)] = "WAITING_FOR_CHILD"
                    elif item.get("tool") == "wait":
                        self._tools[str(item_id)] = "COMPLETED"
            if kind == "turn.completed" and isinstance(value.get("usage"), dict):
                self._usage = {"availability": "AVAILABLE", "source": observation["source_reference"], **value["usage"]}
            if kind in ("thread.started", "turn.started", "turn.completed", "turn.failed", "item.started", "item.updated", "item.completed", "error"):
                self._last_progress = time.monotonic()
                self.event("CODEX_OFFICIAL_EVENT_OBSERVED", observation)

    def publish(self, broker=None, watchdog=None, workspace=None, *, secret_values=()):
        activity = broker.activity_snapshot() if broker and hasattr(broker, "activity_snapshot") else {}
        states = list(activity.get("active_requests", []))
        liveness = []
        for request in states:
            liveness.append(request.get("activity", "ACTIVE_MODEL_REQUEST"))
        advice = activity.get("rate_limit_advice")
        if advice and time.time() < advice.get("backoff_until", 0):
            liveness.append("RATE_LIMIT_BACKOFF")
        if "WAITING_FOR_CHILD" in self._tools.values():
            liveness.append("WAITING_FOR_CHILD")
        if "RUNNING" in self._tools.values():
            liveness.append("LOCAL_TOOL_RUNNING")
        if any(isinstance(value, dict) and value.get("status") == "running" for value in self._children.values()):
            liveness.append("CHILD_AGENT_RUNNING")
        if not liveness and time.monotonic() - self._last_progress > 60:
            liveness.append("POSSIBLE_STALL")
        patch = {"availability": "UNAVAILABLE", "readiness": "UNVERIFIED"}
        if workspace:
            try:
                tree = _source_snapshot(Path(workspace))
                if any(secret.encode() in data for secret in secret_values if secret for data in tree.values()):
                    raise ValueError("Credentials are forbidden in observed source")
                hashes = {name: sha256(data).hexdigest() for name, data in tree.items()}
                from benchmark.submission import source_tree_sha256
                patch = {"availability": "AVAILABLE", "files_sha256": hashes,
                         "observed_tree_sha256": source_tree_sha256(tree),
                         "readiness": "UNVERIFIED", "atomic_tree": False}
                if self.baseline_tree_sha256 and patch["observed_tree_sha256"] != self.baseline_tree_sha256 and self._first_patch_observed is None:
                    self._first_patch_observed = {"observed_at": _now(),
                        "source_tree_sha256": patch["observed_tree_sha256"],
                        "hidden_test_readiness": "UNVERIFIED", "atomic_tree": False}
                    self.event("PATCH_TREE_CHANGE_FIRST_OBSERVED", self._first_patch_observed)
            except (OSError, ValueError):
                patch["reason"] = "UNSAFE_OR_CHANGING_SOURCE"
        self._snapshot = {**self.control, "status": "RUNNING", "evidence_status": "PARTIAL_SNAPSHOT",
                          "observed_at": _now(), "liveness_states": sorted(set(liveness)),
                          "last_trusted_progress": self._recent, "child_states": redact(self._children),
                          "usage": self._usage, "model_channel": activity,
                          "resource_observations": watchdog.snapshot() if watchdog else "UNAVAILABLE",
                          "patch_snapshot": patch, "first_patch_observed": self._first_patch_observed}
        _atomic(self.archive / "runtime_status.json", self._snapshot)

    def finish(self, result, failure_kind=None, runtime_metadata=None):
        self.event("PROCESS_EXITED", {"runtime_result": result, "failure_kind": failure_kind})
        if runtime_metadata:
            channel = runtime_metadata.get("model_broker", {})
            channel = {key: value for key, value in channel.items() if key not in ("request_records", "errors")} if isinstance(channel, dict) else "UNAVAILABLE"
            self._snapshot.update(model_channel=channel,
                resource_observations=runtime_metadata.get("resource_watchdog", "UNAVAILABLE"),
                usage=runtime_metadata.get("usage", {"availability": "UNAVAILABLE"}),
                verified_subagents=runtime_metadata.get("subagents", {"availability": "UNAVAILABLE"}))
        _atomic(self.archive / "runtime_status.json", {**self._snapshot, "status": result,
                "ended_at": _now(), "failure_kind": failure_kind,
                "evidence_status": "FINAL_RUNTIME_SNAPSHOT"})
        self._output.close()
        for signum, previous in self._handlers.items():
            signal.signal(signum, previous)


def _source_snapshot(workspace: Path) -> dict[str, bytes]:
    """Read a live untrusted tree through pinned directory FDs, never symlinks.

    The final submission collector runs after writers stop. A live snapshot
    cannot use path-based opens: a candidate can swap a parent after validation.
    O_NONBLOCK prevents a FIFO replacement from making status/cancel hang.
    """
    from benchmark.submission import MAX_SOURCE_BYTES, MAX_SOURCE_FILES, MAX_TREE_ENTRIES
    root = _directory(workspace)
    tree, total, count = {}, 0, 0
    workspace_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        app_fd = os.open("app", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=workspace_fd)
        def walk(directory_fd, prefix):
            nonlocal total, count
            if prefix.count("/") > 64:
                raise ValueError("Source snapshot nesting limit exceeded")
            with os.scandir(directory_fd) as entries:
                items = []
                for entry in entries:
                    items.append(entry)
                    if count + len(items) > MAX_TREE_ENTRIES:
                        raise ValueError("Source snapshot entry limit exceeded")
                items.sort(key=lambda entry: entry.name)
            for entry in items:
                count += 1
                if count > MAX_TREE_ENTRIES:
                    raise ValueError("Source snapshot entry limit exceeded")
                mode = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(mode.st_mode):
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)
                    try:
                        walk(child, prefix + entry.name + "/")
                    finally:
                        os.close(child)
                    continue
                if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
                    raise ValueError("Unsafe live source entry")
                if not entry.name.endswith(".py"):
                    continue
                descriptor = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory_fd)
                try:
                    before = os.fstat(descriptor)
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_SOURCE_BYTES or (before.st_dev, before.st_ino) != (mode.st_dev, mode.st_ino):
                        raise ValueError("Source changed to an unsafe entry")
                    chunks, size = [], 0
                    while size <= MAX_SOURCE_BYTES:
                        block = os.read(descriptor, min(65536, MAX_SOURCE_BYTES + 1 - size))
                        if not block:
                            break
                        chunks.append(block); size += len(block)
                    after = os.fstat(descriptor)
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise ValueError("Source changed during snapshot")
                finally:
                    os.close(descriptor)
                data = b"".join(chunks)
                total += len(data)
                if size > MAX_SOURCE_BYTES or total > MAX_SOURCE_BYTES or len(tree) >= MAX_SOURCE_FILES:
                    raise ValueError("Source snapshot byte/file limit exceeded")
                tree[prefix + entry.name] = data
        try:
            walk(app_fd, "app/")
        finally:
            os.close(app_fd)
    finally:
        os.close(workspace_fd)
    return tree
