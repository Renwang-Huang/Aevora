"""Trusted independent-OS-worker scheduling over the existing business RPC.

This is candidate execution topology, not an Agent orchestrator. It never
imports candidate code, decides inventory truth, or substitutes a repair.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from uuid import uuid4

from benchmark.resources import CANDIDATE_LIMITS, CgroupScope, ResourceWatchdog
from evaluator.control import WorkerControl, process_identity
from evaluator.rpc import BusinessRPC, RemoteBusinessError, RemoteExecutionError


class WorkerSupervisor:
    def __init__(self, workspace: Path, data_dir: Path, artifacts: Path, *,
                 worker_count: int = 2, require_cgroup: bool = True):
        if type(worker_count) is not int or worker_count not in (2, 4):
            raise ValueError("Worker topology must contain exactly two or four processes")
        if type(require_cgroup) is not bool:
            raise ValueError("require_cgroup must be boolean")
        self.workspace, self.data_dir, self.artifacts = map(Path, (workspace, data_dir, artifacts))
        self.workspace = self.workspace.resolve(strict=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.data_dir, self.artifacts = self.data_dir.resolve(), self.artifacts.resolve()
        self.worker_count, self.require_cgroup = worker_count, require_cgroup
        self.supervisor_id = str(uuid4())
        self.resource_record_path = self.artifacts / f"pool-resource-{self.supervisor_id}.json"
        self.workers = []
        self.control = None
        self.cgroup = None
        self._watchdogs = {}
        self._records, self._identities, self._resources = [], [], []
        self._fd_witnesses = []
        self._fd_observed_generations = set()
        self._operation_lock = threading.Lock()
        self._record_lock = threading.Lock()
        self._closed = False
        self._cleanup = None
        self.expected_stock = {}
        self._resource_record = None
        self.pool_limits = replace(CANDIDATE_LIMITS,
            memory_bytes=worker_count * CANDIDATE_LIMITS.memory_bytes,
            max_tasks=512)

    def _record(self, event, **details):
        row = {"event": event, "host_observed_ns": time.monotonic_ns(), **details}
        with self._record_lock:
            self._records.append(row)
        return row

    def _verify_ancestry(self, identity, root_pid):
        current, seen = identity["host_pid"], set()
        while current > 1 and current not in seen:
            if current == root_pid:
                return
            seen.add(current)
            current = process_identity(current)["parent_pid"]
        raise RemoteExecutionError("Kernel-identified control peer is not a descendant of its sandbox launch")

    def _start_worker(self, index):
        rpc = self.workers[index]
        self.control.prepare_restart(index)
        rpc.start()
        identity = self.control.wait_ready(index)
        self._verify_ancestry(identity, rpc.process.pid)
        identity.update(launcher_pid=rpc.process.pid, generation=sum(
            row["worker_index"] == index for row in self._identities))
        self._identities.append(identity)
        watchdog = ResourceWatchdog(rpc.process.pid, CANDIDATE_LIMITS,
                                   output_roots=(self.data_dir,)).start()
        self._watchdogs[index] = watchdog
        self._record("worker.started", identity=identity, shared_database=self._database_identity())

    def start(self):
        if self._closed:
            raise ValueError("A finalized worker pool cannot be reopened")
        if any(worker.process is not None for worker in self.workers):
            raise ValueError("Worker pool is already running; stop_all before start")
        try:
            if self.control is None:
                if self.require_cgroup:
                    self.cgroup = CgroupScope.create(self.pool_limits)
                    # Candidate mounts never expose artifacts. The independent
                    # evaluator can recover this owned scope after pytest is
                    # killed before Python finally blocks get an opportunity.
                    self._resource_record = {"record_version": "1.0.0",
                        "source": "trusted_worker_supervisor", "supervisor_id": self.supervisor_id,
                        "owner_uid": os.getuid(), "supervisor_pid": os.getpid(),
                        "supervisor_identity": process_identity(os.getpid()),
                        "created_at_unix_ns": time.time_ns(), "cgroup_path": str(self.cgroup.path),
                        "limits": self.pool_limits.as_dict(), "cleanup_complete": False}
                    self.resource_record_path.write_text(json.dumps(self._resource_record, indent=2) + "\n")
                self.control = WorkerControl(self.worker_count, on_event=self._observe_control_event)
                if self._resource_record is not None:
                    self._resource_record["control_directory"] = str(self.control.directory)
                    self.resource_record_path.write_text(json.dumps(self._resource_record, indent=2) + "\n")
                self.workers = [BusinessRPC(self.workspace, self.data_dir,
                    self.artifacts / f"worker-supervisor-{self.supervisor_id}-{index}.stderr.log",
                    control_socket=self.control.paths[index],
                    command_wrapper=self.cgroup.wrap_command if self.cgroup else None,
                    response_timeout=40) for index in range(self.worker_count)]
            for index in range(self.worker_count):
                self._start_worker(index)
            self.save("started")
            return self
        except BaseException:
            self.close()
            raise

    def initialize(self, stock, reset=True):
        if type(reset) is not bool or not isinstance(stock, dict):
            raise ValueError("Fixture stock must be a mapping and reset a boolean")
        self.expected_stock = dict(stock)
        result = self.call(0, "initialize", stock=stock, reset=reset)
        self._record("fixture.initialized", stock=dict(stock), shared_database=self._database_identity())
        return result

    def _index(self, index):
        if type(index) is not int or not 0 <= index < self.worker_count:
            raise ValueError("Worker index is outside this fixed topology")
        if self.control is None or self._closed:
            raise ValueError("Worker pool is unavailable")

    def call(self, worker_index, method, **params):
        self._index(worker_index)
        started = time.monotonic_ns()
        identity = self.control.wait_ready(worker_index)
        envelope = {"worker_index": worker_index, "host_pid": identity["host_pid"],
                    "start_ns": started, "method": method, "parameters": params}
        try:
            result = self.workers[worker_index].call(method, **params)
            envelope.update(ok=True, result=result)
            return result
        except RemoteBusinessError as error:
            envelope.update(ok=False, error={"type": error.kind, "message": str(error), "source": "candidate"})
            raise
        except Exception as error:
            envelope.update(ok=False, error={"type": type(error).__name__, "message": str(error), "source": "transport"})
            raise
        finally:
            envelope["end_ns"] = time.monotonic_ns()
            self._record("operation.finished", **envelope)

    def batch(self, operations, *, checkpoint=None):
        if not isinstance(operations, list) or not 1 <= len(operations) <= 1000:
            raise ValueError("Process batch must contain between one and 1000 operations")
        for operation in operations:
            if (not isinstance(operation, dict) or set(operation) - {"method", "params"}
                    or not isinstance(operation.get("method"), str)
                    or not isinstance(operation.get("params", {}), dict)):
                raise ValueError("Invalid business operation in process batch")
        if self.control is None:
            raise ValueError("Start the worker pool before executing operations")
        with self._operation_lock:
            parties = min(self.worker_count, len(operations))
            self.control.set_gate(checkpoint, parties)
            start_barrier = threading.Barrier(parties, timeout=5)
            queues = [[] for _ in range(parties)]
            for index, operation in enumerate(operations):
                queues[index % parties].append((index, operation))
            started = time.monotonic_ns()

            def execute(index):
                start_barrier.wait()
                output = []
                for request_index, operation in queues[index]:
                    item = {"index": request_index, "worker_index": index,
                            "host_pid": self.control.wait_ready(index)["host_pid"],
                            "start_ns": time.monotonic_ns()}
                    try:
                        item.update(ok=True, result=self.call(index, operation["method"], **operation.get("params", {})))
                    except RemoteBusinessError as error:
                        item.update(ok=False, error={"type": error.kind, "message": str(error), "source": "candidate"})
                    except RemoteExecutionError as error:
                        item.update(ok=False, error={"type": type(error).__name__, "message": str(error), "source": "transport"})
                    item["end_ns"] = time.monotonic_ns()
                    output.append(item)
                return output

            try:
                with ThreadPoolExecutor(max_workers=parties, thread_name_prefix="orderflow-host-dispatch") as pool:
                    grouped = list(pool.map(execute, range(parties)))
                result = {"results": sorted([row for group in grouped for row in group], key=lambda row: row["index"]),
                          "execution": {"worker_count": self.worker_count,
                              "worker_identities": [self.control.wait_ready(index) for index in range(parties)],
                              "shared_database": self._database_identity(), "clock": "host_monotonic_ns",
                              "start_ns": started, "end_ns": time.monotonic_ns(),
                              "checkpoint": self.control.gate_observation(), "dispatch": "fixed_round_robin",
                              "operations": len(operations)}}
                self._record("batch.finished", observation=result)
                self.save("batch")
                return result
            finally:
                self.control.set_gate(None, parties)

    def arm_stop(self, worker_index, label):
        self._index(worker_index)
        self.control.arm_stop(worker_index, label)

    def wait_stop(self, worker_index, timeout=5):
        self._index(worker_index)
        if type(timeout) not in (int, float) or not 0 < timeout <= 5:
            raise ValueError("Stop wait must be in (0, 5]")
        return self.control.wait_stop(worker_index, timeout)

    def release(self, worker_index):
        self._index(worker_index)
        self.control.release(worker_index)

    def disarm(self, worker_index):
        self._index(worker_index)
        self.control.disarm(worker_index)

    def kill(self, worker_index):
        self._index(worker_index)
        record = self.control.kill(worker_index)
        self.workers[worker_index].close()
        record["launcher_exit_code"] = self.workers[worker_index].last_exit_code
        watchdog = self._watchdogs.pop(worker_index, None)
        if watchdog is not None:
            self._resources.append({"worker_index": worker_index, **watchdog.close(cleanup=True)})
        self._record("worker.killed", worker_index=worker_index, observation=record)
        self.save("killed")
        return record

    def restart(self, worker_index):
        self._index(worker_index)
        self.control.disarm(worker_index)
        self.workers[worker_index].close()
        watchdog = self._watchdogs.pop(worker_index, None)
        if watchdog is not None:
            self._resources.append({"worker_index": worker_index, **watchdog.close(cleanup=True)})
        self._start_worker(worker_index)
        self.save("restarted")
        return self.control.wait_ready(worker_index)

    def crash_call(self, worker_index, method, label, **params):
        """Run a real operation, kill at a reached observer, preserve unknown ack.

        If an optional transaction observer is absent and the call completes,
        return UNAVAILABLE promptly. Never turn absence into a business failure.
        """
        self.arm_stop(worker_index, label)
        started = time.monotonic_ns()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.call, worker_index, method, **params)
            deadline = time.monotonic() + 5
            observation = None
            while time.monotonic() < deadline:
                observation = self.control.wait_stop(worker_index, 0.02)
                if observation["availability"] == "AVAILABLE" or future.done():
                    break
            killed = self.kill(worker_index) if observation["availability"] == "AVAILABLE" else None
            if killed is None:
                self.disarm(worker_index)
            try:
                result = future.result(timeout=40)
                outcome = {"ok": True, "result": result, "response_available": True}
            except Exception as error:
                outcome = {"ok": False, "error": {"type": type(error).__name__, "message": str(error)},
                           "response_available": False if killed is not None else "UNAVAILABLE"}
        result = {**observation, "kill": killed, "request_outcome": outcome,
                  "interval": {"start_ns": started, "end_ns": time.monotonic_ns()}}
        self._record("crash.finished", observation=result)
        self.save("crash")
        return result

    def _database_identity(self):
        database = self.data_dir / "business.sqlite"
        try:
            row = database.lstat()
            if not stat.S_ISREG(row.st_mode) or row.st_nlink != 1:
                return {"availability": "UNSAFE", "path": str(database)}
            return {"availability": "AVAILABLE", "path": str(database),
                    "device": row.st_dev, "inode": row.st_ino, "links": row.st_nlink,
                    "size": row.st_size}
        except FileNotFoundError:
            return {"availability": "UNAVAILABLE", "path": str(database), "reason": "not_initialized"}

    def _observe_control_event(self, event):
        method = event.get("metadata", {}).get("method")
        if event["event"] != "before_commit" or method not in {
                "create_order", "reserve_inventory", "cancel_order", "release_inventory"}:
            return
        # The candidate is synchronously waiting for the generic worker's
        # response, so its transaction connection still has the DB FD open.
        key = (event["worker_index"], event["host_pid"], method)
        with self._record_lock:
            if key in self._fd_observed_generations:
                return
            self._fd_observed_generations.add(key)
        proof = self.database_fds(event["worker_index"])
        proof.update(event_reference={"event": event["event"], "host_observed_ns": event["host_observed_ns"]},
                     worker_index=event["worker_index"], method=method, host_observed_ns=time.monotonic_ns())
        with self._record_lock:
            self._fd_witnesses.append(proof)

    def database_fds(self, worker_index):
        """Host-observed open FD identity, usually sampled at a transaction gate."""
        self._index(worker_index)
        identity = self.control.wait_ready(worker_index)
        database = self._database_identity()
        matches = []
        try:
            for fd in (Path("/proc") / str(identity["host_pid"]) / "fd").iterdir():
                try:
                    row = fd.stat()
                    if (row.st_dev, row.st_ino) == (database.get("device"), database.get("inode")):
                        matches.append({"fd": int(fd.name), "device": row.st_dev, "inode": row.st_ino})
                except OSError:
                    continue
            return {"availability": "AVAILABLE", "identity": identity, "database": database, "matching_fds": matches}
        except OSError as error:
            return {"availability": "UNAVAILABLE", "identity": identity, "reason": type(error).__name__}

    def stop_all(self):
        if self.control is not None:
            for index in range(self.worker_count):
                self.control.disarm(index)
        for index, worker in enumerate(self.workers):
            returncode = worker.process.poll() if worker.process is not None else None
            worker.close()
            watchdog = self._watchdogs.pop(index, None)
            if watchdog is not None:
                self._resources.append({"worker_index": index, **watchdog.close(cleanup=True)})
            self._record("worker.stopped", worker_index=index, pre_close_exit_code=returncode)
            self._record("worker.exit", worker_index=index, launcher_exit_code=worker.last_exit_code)
        self.save("stopped")

    def evidence(self):
        with self._record_lock:
            records = list(self._records)
        return {"supervisor_version": "1.0.0", "worker_count": self.worker_count,
                "supervisor_id": self.supervisor_id,
                "stock": dict(self.expected_stock), "shared_database": self._database_identity(),
                "identity_generations": list(self._identities), "records": records,
                "database_fd_witnesses": list(self._fd_witnesses),
                "control": self.control.observation() if self.control is not None else None,
                "resources": list(self._resources),
                "pool_cgroup": self.cgroup.metadata if self.cgroup is not None else {
                    "availability": "UNAVAILABLE_SECURITY_GATE" if self.require_cgroup else "DISABLED_EXPLICITLY",
                    "limitations": "No pool kernel memory/pids gate"},
                "cleanup": self._cleanup,
                "limitations": ["PID values are scoped to the trusted supervisor namespace",
                    "Transaction observer covers common Python SQLite APIs and target database row writes; opaque/native bypasses are UNAVAILABLE",
                    "CPU/output aggregate monitoring retains Phase 3.5 sampled limitations"]}

    def save(self, label="observation"):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", label)[:120] or "observation"
        path = self.artifacts / f"topology-{self.supervisor_id}-{safe}.json"
        path.write_text(json.dumps(self.evidence(), indent=2, sort_keys=True) + "\n")
        return path

    def close(self):
        if self._closed:
            return self.evidence()
        try:
            self.stop_all()
        finally:
            if self.control is not None:
                self.control.close()
            cgroup = self.cgroup.close() if self.cgroup is not None else None
            self._closed = True
            remaining = [pid for resource in self._resources for pid in resource.get("remaining_pids", [])]
            self._cleanup = {"complete": not remaining and (cgroup is None or cgroup["cleanup_complete"]),
                             "remaining_pids": remaining,
                             "control_directory_removed": self.control is None or not self.control.directory.exists()}
            if self._resource_record is not None:
                self._resource_record.update(cleanup_complete=self._cleanup["complete"],
                    cleanup_at_unix_ns=time.time_ns(), cgroup_final=cgroup,
                    control_directory_removed=self._cleanup["control_directory_removed"])
                self.resource_record_path.write_text(json.dumps(self._resource_record, indent=2) + "\n")
            self.save("cleanup")
        return self.evidence()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
