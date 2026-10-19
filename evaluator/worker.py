"""Generic business RPC endpoint mounted alone in a candidate sandbox.

This file contains no assertions, expected outcomes, or hidden test source.
The host evaluator sends ordinary business operations over JSON lines.
"""

import contextlib
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
import socket
import sqlite3
import sqlite3.dbapi2
import re
import weakref
import sys
import threading
import time


class WorkerControlClient:
    """Fixed scheduling-only protocol; no private evaluator logic is mounted."""
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(10)
        self.socket.connect(path)
        self.stream = self.socket.makefile("rb")
        self._lock = threading.Lock()
        self.method = None
        self.notify("hello", protocol_version=1, namespace_pid=os.getpid())

    def notify(self, event, **metadata):
        metadata.setdefault("method", self.method)
        message = json.dumps({"event": event, "metadata": metadata}, ensure_ascii=True).encode() + b"\n"
        if len(message) > 16384:
            raise ValueError("Control observation exceeds its bounded size")
        with self._lock:
            self.socket.sendall(message)
            response = self.stream.readline(16385)
            if not response or len(response) > 16384 or json.loads(response) != {"command": "continue"}:
                raise RuntimeError("Worker scheduling channel closed or violated its fixed protocol")

    def checkpoint(self, label):
        self.notify("checkpoint", label=label)

    def close(self):
        self.stream.close()
        self.socket.close()


def sql_verb(statement):
    text = statement.lstrip(" \t\r\n\f\v\ufeff;")
    while text.startswith(("--", "/*")):
        if text.startswith("--"):
            split = text.find("\n")
            text = "" if split < 0 else text[split + 1:].lstrip()
        else:
            split = text.find("*/")
            text = "" if split < 0 else text[split + 2:].lstrip()
    token = re.match(r"[A-Za-z_]+", text)
    return token.group().upper() if token is not None else ""


class SQLiteObserver:
    VERSION = "1.1.0"

    def __init__(self, notify, database_path=None):
        self.notify = notify
        self.database_path = database_path
        self.original_connect = sqlite3.connect
        self.original_dbapi_connect = sqlite3.dbapi2.connect
        self.base_connection, self.base_cursor = sqlite3.Connection, sqlite3.Cursor
        self.connections = weakref.WeakSet()
        self.unavailable = []
        self.errors = []
        self._connection_types, self._cursor_types = {}, {}
        self._sequence = 0
        self._target_count = 0

    def observation(self):
        return {"version": self.VERSION, "connections_observed": self._sequence,
                "target_connections_observed": self._target_count,
                "availability": "AVAILABLE" if self._target_count and not self.errors and not self.unavailable else "UNAVAILABLE",
                "errors": self.errors[:8], "error_count": len(self.errors),
                "unavailable": self.unavailable[:8],
                "supported": ["connection.commit", "SQL COMMIT/END", "cursor SQL COMMIT/END",
                              "connection context exit", "explicit-transaction scripts", "subclass factories",
                              "autocommit statement DONE/fetch EOF/cursor close"],
                "unsupported": ["direct _sqlite3/Connection C entrypoints and unbound close", "opaque callable factories",
                                "autocommit batch per-statement boundaries", "native SQLite clients",
                                "DDL-only commits", "outermost SAVEPOINT release"]}

    def _unavailable(self, reason):
        record = {"reason": reason}
        if record not in self.unavailable and len(self.unavailable) < 32:
            self.unavailable.append(record)

    def _error(self, error, source):
        if len(self.errors) < 32:
            self.errors.append({"source": source, "type": type(error).__name__, "message": str(error)[:300]})

    def install(self):
        manager = self

        def connect(*args, **kwargs):
            factory = args[5] if len(args) > 5 else kwargs.get("factory", manager.base_connection)
            if isinstance(factory, type) and issubclass(factory, manager.base_connection):
                factory = manager.connection_type(factory)
                if len(args) > 5:
                    args = (*args[:5], factory, *args[6:])
                else:
                    kwargs["factory"] = factory
            else:
                # A callable that returns an opaque C connection is preserved,
                # never rejected just to force a particular legal repair.
                manager._unavailable("opaque_callable_connection_factory")
            return manager.original_connect(*args, **kwargs)

        self.wrapped_connect = connect
        sqlite3.connect = sqlite3.dbapi2.connect = connect
        return self

    def uninstall(self):
        if sqlite3.connect is self.wrapped_connect:
            sqlite3.connect = self.original_connect
        if sqlite3.dbapi2.connect is self.wrapped_connect:
            sqlite3.dbapi2.connect = self.original_dbapi_connect

    def connection_type(self, base):
        if base in self._connection_types:
            return self._connection_types[base]
        manager = self

        class ConnectionMixin:
            def __init__(self, *args, **kwargs):
                manager._sequence += 1
                self._observation_id = manager._sequence
                self._user_trace = None
                self._pending_commit = False
                self._pending_auto = None
                self._transaction_changes = 0
                self._active_auto_cursors = weakref.WeakSet()
                self._autocommit_batch_depth = 0
                self._commit_sequence = 0
                self._eligible = False
                # Custom subclass constructors may call execute after their
                # native initialization. Preserve those calls without touching
                # undefined wrapper state or pretending earlier writes observed.
                super().__init__(*args, **kwargs)
                if self.total_changes:
                    manager._unavailable("custom_constructor_prior_write_boundary")
                self._transaction_changes = self.total_changes
                self._eligible = manager.database_path is None
                if manager.database_path is not None:
                    try:
                        cursor = manager.base_connection.cursor(self)
                        cursor.row_factory = None
                        try:
                            databases = manager.base_cursor.execute(cursor, "PRAGMA database_list").fetchall()
                        finally:
                            manager.base_cursor.close(cursor)
                        target = os.stat(manager.database_path)
                        self._eligible = any(name == "main" and filename and
                                             (os.stat(filename).st_dev, os.stat(filename).st_ino) == (target.st_dev, target.st_ino)
                                             for _, name, filename in databases)
                        if len(databases) > 1:
                            manager._unavailable("attached_database_write_attribution")
                    except Exception as error:
                        manager._error(error, "target_database_identity")
                if self._eligible:
                    manager._target_count += 1
                manager.connections.add(self)
                super().set_trace_callback(self._observe_trace)

            def _emit(self, event, source):
                if not self._eligible:
                    return
                try:
                    manager.notify(event, sqlite_observer_version=manager.VERSION,
                                   connection_id=self._observation_id, boundary_source=source,
                                   in_transaction=self.in_transaction,
                                   write_observed=True, target_database=True)
                except Exception as error:
                    # CPython suppresses exceptions raised from trace callbacks.
                    # Record our failures explicitly without changing SQLite's
                    # normal business semantics or claiming complete evidence.
                    manager._error(error, source)

            def _observe_trace(self, statement):
                # Trace runs before the current SQL. The prior COMMIT is proved
                # only when SQLite has already left that transaction. This is
                # also the safe boundary between COMMIT and BEGIN in scripts
                # and in Python 3.12 autocommit=False.
                try:
                    self._flush_commit("next_statement_after_commit")
                    verb = sql_verb(statement)
                    if verb in {"COMMIT", "END"}:
                        if self.in_transaction and self.total_changes > self._transaction_changes:
                            self._emit("before_commit", "sqlite_trace_before_commit")
                            self._pending_commit = True
                    elif verb in {"BEGIN", "ROLLBACK"}:
                        self._pending_commit = False
                        self._pending_auto = None
                        self._transaction_changes = self.total_changes
                    elif verb in {"SAVEPOINT", "RELEASE"}:
                        manager._unavailable("savepoint_commit_boundary")
                    elif verb == "ATTACH":
                        manager._unavailable("attached_database_write_attribution")
                    elif (self._autocommit_batch_depth and not self.in_transaction
                          and verb in {"INSERT", "UPDATE", "DELETE", "REPLACE", "WITH"}):
                        manager._unavailable("autocommit_batch_per_statement_boundary")
                    # Never flush auto-writes from a trace: trigger statements
                    # run inside unfinished parent statements, and SQLite's
                    # autocommit flag alone does not prove statement DONE.
                except Exception as error:
                    manager._error(error, "internal_sqlite_trace")
                if self._user_trace is not None:
                    self._user_trace(statement)

            def _flush_commit(self, source):
                if self._pending_commit and not self.in_transaction:
                    self._pending_commit = False
                    self._pending_auto = None
                    self._transaction_changes = self.total_changes
                    self._commit_sequence += 1
                    self._emit("transaction_committed", source)

            def _flush_auto(self, source):
                if (self._pending_auto is not None and not self.in_transaction
                        and not self._active_auto_cursors
                        and self.total_changes > self._pending_auto):
                    self._pending_auto = None
                    self._emit("transaction_committed", source)

            def _observe_call(self, action, source, *args, **kwargs):
                try:
                    result = action(*args, **kwargs)
                except BaseException:
                    # A traced COMMIT whose real call failed is not evidence of
                    # a commit. In particular preserve deferred-FK and busy
                    # errors, and never turn subsequent rollback into success.
                    self._pending_commit = False
                    self._pending_auto = None
                    raise
                self._flush_commit(source)
                return result

            def set_trace_callback(self, callback):
                self._user_trace = callback
                return super().set_trace_callback(self._observe_trace)

            def cursor(self, factory=None):
                factory = manager.base_cursor if factory is None else factory
                if isinstance(factory, type) and issubclass(factory, manager.base_cursor):
                    factory = manager.cursor_type(factory)
                else:
                    manager._unavailable("opaque_callable_cursor_factory")
                return super().cursor(factory)

            def execute(self, *args, **kwargs):
                # CPython's C shortcuts do not call the Python cursor override.
                # Preserve any supplied custom Connection override; the default
                # shortcut uses our subclass cursor so fetch/close are observed.
                if base.execute is manager.base_connection.execute:
                    return self.cursor().execute(*args, **kwargs)
                return self._observe_call(super().execute, "connection_execute_returned", *args, **kwargs)

            def executemany(self, *args, **kwargs):
                if base.executemany is manager.base_connection.executemany:
                    return self.cursor().executemany(*args, **kwargs)
                return self._observe_call(super().executemany, "connection_executemany_returned", *args, **kwargs)

            def executescript(self, *args, **kwargs):
                if base.executescript is manager.base_connection.executescript:
                    return self.cursor().executescript(*args, **kwargs)
                return self._observe_call(super().executescript, "connection_executescript_returned", *args, **kwargs)

            def commit(self):
                return self._observe_call(super().commit, "connection_commit_returned")

            def rollback(self):
                self._pending_commit = self._pending_auto = None
                result = super().rollback()
                self._transaction_changes = self.total_changes
                return result

            def __exit__(self, *args):
                return self._observe_call(super().__exit__, "connection_context_exit_returned", *args)

            def close(self):
                # Even a direct sqlite3.Connection.commit(self) call is proved
                # here if its real COMMIT finished before wrapped close.
                self._flush_commit("connection_close_after_commit")
                if self._active_auto_cursors:
                    manager._unavailable("connection_close_with_active_autocommit_statement")
                return super().close()

        observed = type("Observed" + base.__name__, (ConnectionMixin, base), {})
        self._connection_types[base] = observed
        return observed

    def cursor_type(self, base):
        if base in self._cursor_types:
            return self._cursor_types[base]

        manager = self

        class CursorMixin:
            def _write_action(self, action, source, args, kwargs, batch=False):
                connection = self.connection
                before = connection.total_changes
                commit_sequence = connection._commit_sequence
                auto = not connection.in_transaction
                if batch:
                    connection._autocommit_batch_depth += 1
                try:
                    result = connection._observe_call(action, source, *args, **kwargs)
                finally:
                    if batch:
                        connection._autocommit_batch_depth -= 1
                if auto and not connection.in_transaction:
                    if commit_sequence != connection._commit_sequence:
                        before = connection._transaction_changes
                    if connection._pending_auto is None:
                        connection._pending_auto = before
                    # Result-bearing SQL may still be executing even when
                    # in_transaction=False. Defer until EOF/finalization.
                    verb = sql_verb(args[0]) if args else ""
                    potential_write = verb not in {"SELECT", "PRAGMA", "EXPLAIN", "VALUES", "COMMIT", "END", "ROLLBACK"}
                    if self.description is not None and not batch and potential_write:
                        connection._active_auto_cursors.add(self)
                    else:
                        connection._active_auto_cursors.discard(self)
                        connection._flush_auto(source)
                return result

            def _completed(self, source):
                self.connection._active_auto_cursors.discard(self)
                self.connection._flush_auto(source)

            def execute(self, *args, **kwargs):
                return self._write_action(super().execute, "cursor_execute_returned", args, kwargs)

            def executemany(self, *args, **kwargs):
                return self._write_action(super().executemany, "cursor_executemany_returned", args, kwargs, batch=True)

            def executescript(self, *args, **kwargs):
                return self._write_action(super().executescript, "cursor_executescript_returned", args, kwargs, batch=True)

            def fetchone(self):
                result = self.connection._observe_call(super().fetchone, "cursor_fetchone_returned")
                if result is None:
                    self._completed("cursor_fetchone_EOF")
                return result

            def fetchmany(self, *args, **kwargs):
                result = self.connection._observe_call(super().fetchmany, "cursor_fetchmany_returned", *args, **kwargs)
                size = args[0] if args else kwargs.get("size", self.arraysize)
                if size > 0 and len(result) < size:
                    self._completed("cursor_fetchmany_EOF")
                return result

            def fetchall(self):
                result = self.connection._observe_call(super().fetchall, "cursor_fetchall_returned")
                self._completed("cursor_fetchall_EOF")
                return result

            def __next__(self):
                try:
                    result = super().__next__()
                except StopIteration:
                    self.connection._flush_commit("cursor_iteration_completed")
                    self._completed("cursor_iteration_EOF")
                    raise
                self.connection._flush_commit("cursor_iteration_step_returned")
                return result

            def close(self):
                result = self.connection._observe_call(super().close, "cursor_close_returned")
                self._completed("cursor_close_finalized")
                return result

        observed = type("Observed" + base.__name__, (CursorMixin, base), {})
        self._cursor_types[base] = observed
        return observed


def write_message(message: dict) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def error_message(error: Exception) -> dict:
    return {"type": type(error).__name__, "message": str(error)[:2000]}


class ScheduleCheckpoint:
    """A bounded, optional observation gate for a batch's first wave.

    Candidate operations may call the injected ``_schedule_checkpoint(label)``
    after a read. Operations that do not use it run normally. A lock-based
    implementation can reach the gate one thread at a time: timeout permanently
    releases the gate rather than declaring a business error or deadlocking it.
    This class contains scheduling instrumentation, never business assertions.
    """

    def __init__(self, label: str, parties: int, timeout_seconds: float):
        self.label = label
        self.parties = parties
        self.timeout_seconds = timeout_seconds
        self.local = threading.local()
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._arrivals: set[int] = set()
        self._waiters = 0
        self._waiters_peak = 0
        self._released_by: str | None = None

    def __call__(self, label: str) -> None:
        # Queued operations must not join a barrier that waits for occupied
        # executor slots. Only the first wave participates, once per thread.
        if label != self.label or not getattr(self.local, "first_wave", False):
            return
        thread_id = threading.get_ident()
        with self._lock:
            if thread_id in self._arrivals:
                return
            self._arrivals.add(thread_id)
            if len(self._arrivals) == self.parties and not self._event.is_set():
                self._released_by = "all_arrived"
                self._event.set()
            if self._event.is_set():
                return
            self._waiters += 1
            self._waiters_peak = max(self._waiters_peak, self._waiters)
        try:
            if not self._event.wait(self.timeout_seconds):
                with self._lock:
                    if not self._event.is_set():
                        self._released_by = "timeout"
                        self._event.set()
        finally:
            with self._lock:
                self._waiters -= 1

    def observation(self) -> dict:
        with self._lock:
            return {
                "label": self.label,
                "parties": self.parties,
                "timeout_seconds": self.timeout_seconds,
                "arrivals": len(self._arrivals),
                "arrival_thread_ids": sorted(self._arrivals),
                "released_by": self._released_by or "unused",
                "waiters_peak": self._waiters_peak,
            }


def execute_batch(flow, methods: dict, operations: list, max_workers: int,
                  synchronize_start: bool = True, checkpoint: dict | None = None) -> dict:
    """Invoke independent public operations on one flow object in real threads."""
    if not isinstance(operations, list) or not 1 <= len(operations) <= 1000:
        raise ValueError("batch operations must contain between 1 and 1000 requests")
    if type(max_workers) is not int or not 1 <= max_workers <= 256:
        raise ValueError("batch max_workers must be an integer between 1 and 256")
    if type(synchronize_start) is not bool:
        raise ValueError("batch synchronize_start must be a boolean")
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Each batch operation must be an object")
        if operation.get("method") not in methods or not isinstance(operation.get("params", {}), dict):
            raise ValueError("Unknown batch method or invalid parameters")
    parties = min(max_workers, len(operations))
    gate = None
    if checkpoint is not None:
        if not isinstance(checkpoint, dict):
            raise ValueError("batch checkpoint must be an object or null")
        label = checkpoint.get("label")
        timeout = checkpoint.get("timeout_seconds", 2.0)
        if not isinstance(label, str) or not label.strip():
            raise ValueError("checkpoint label must be a nonempty string")
        if (type(timeout) not in (float, int) or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError("checkpoint timeout_seconds must be a finite positive number")
        gate = ScheduleCheckpoint(label, parties, float(timeout))

    start_barrier = threading.Barrier(parties) if synchronize_start else None
    state_lock = threading.Lock()
    thread_ids: set[int] = set()
    active = 0
    max_active = 0
    missing = object()
    prior_checkpoint = getattr(flow, "_schedule_checkpoint", missing)

    def invoke(index: int, operation: dict) -> dict:
        nonlocal active, max_active
        thread_id = threading.get_ident()
        if gate is not None:
            gate.local.first_wave = index < parties
        if start_barrier is not None and index < parties:
            start_barrier.wait()
        started_ns = time.monotonic_ns()
        with state_lock:
            thread_ids.add(thread_id)
            active += 1
            max_active = max(max_active, active)
        envelope = {"index": index, "pid": os.getpid(), "thread_id": thread_id,
                    "start_ns": started_ns}
        try:
            envelope.update(ok=True, result=methods[operation["method"]](**operation.get("params", {})))
        except Exception as error:
            envelope.update(ok=False, error=error_message(error))
        finally:
            envelope["end_ns"] = time.monotonic_ns()
            with state_lock:
                active -= 1
            if gate is not None:
                gate.local.first_wave = False
        return envelope

    started_ns = time.monotonic_ns()
    if gate is not None:
        flow._schedule_checkpoint = gate
    try:
        with ThreadPoolExecutor(max_workers=parties, thread_name_prefix="orderflow-rpc") as executor:
            futures = [executor.submit(invoke, index, operation)
                       for index, operation in enumerate(operations)]
            results = [future.result() for future in futures]
    finally:
        if gate is not None:
            if prior_checkpoint is missing:
                del flow._schedule_checkpoint
            else:
                flow._schedule_checkpoint = prior_checkpoint
    return {
        "results": results,
        "execution": {"pid": os.getpid(), "thread_ids": sorted(thread_ids),
                      "max_active": max_active, "operations": len(operations),
                      "max_workers": parties, "synchronize_start": synchronize_start,
                      "clock": "monotonic_ns", "start_ns": started_ns,
                      "end_ns": time.monotonic_ns(),
                      "checkpoint": gate.observation() if gate is not None else None},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-socket")
    arguments = parser.parse_args()
    # The kernel-visible connection is established before candidate import.
    control = WorkerControlClient(arguments.control_socket) if arguments.control_socket else None
    sqlite_observer = SQLiteObserver(control.notify, "/data/business.sqlite").install() if control is not None else None
    sys.path.insert(0, "/workspace")
    try:
        # Application prints must not corrupt the transport stream.
        with contextlib.redirect_stdout(sys.stderr):
            from app.service import OrderFlow

            flow = OrderFlow("/data/business.sqlite")
            if control is not None:
                flow._schedule_checkpoint = control.checkpoint
    except Exception as error:
        write_message({"ready": False, "error": error_message(error)})
        return 2

    methods = {
        "initialize": flow.initialize,
        "create_order": flow.create_order,
        "cancel_order": flow.cancel_order,
        "reserve_inventory": flow.reserve_inventory,
        "release_inventory": flow.release_inventory,
        "get_order": flow.get_order,
        "get_inventory": flow.get_inventory,
        "audit": flow.audit,
    }
    write_message({"ready": True, "protocol_version": 1})
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("RPC request must be an object")
            request_id = request.get("id")
            method = request["method"]
            parameters = request.get("params", {})
            if (method not in methods and method != "batch") or not isinstance(parameters, dict):
                raise ValueError("Unknown RPC method or invalid parameters")
            execution = request.get("execution", {})
            if not isinstance(execution, dict) or execution:
                raise ValueError("Unknown worker execution options")
            if control is not None:
                control.method = method
            # Redirection is process-global, so apply it once around the batch,
            # never independently from executor threads.
            with contextlib.redirect_stdout(sys.stderr):
                if method == "batch":
                    result = execute_batch(flow, methods, **parameters)
                else:
                    result = methods[method](**parameters)
            if control is not None:
                control.notify("before_response", ok=True,
                               transaction_observer=sqlite_observer is not None,
                               sqlite_observer=sqlite_observer.observation())
            write_message({"id": request_id, "ok": True, "result": result})
        except Exception as error:
            if control is not None:
                control.notify("before_response", ok=False,
                               transaction_observer=sqlite_observer is not None,
                               sqlite_observer=sqlite_observer.observation())
            write_message({"id": request_id, "ok": False, "error": error_message(error)})
    if control is not None:
        control.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
